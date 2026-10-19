"""Local models, loaded lazily from ``AI_MODELS_DIR`` (prepared by ``fetch_models.py``).

Every model runs on this server (NFR-10, NFR-11): nothing is sent to an outside service.
Each capability is independent; a missing model only disables its own endpoint (503).
"""

import json
import re
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

from app.config import get_settings

ALLOWED_SPEECH_LANGUAGES = ("ar", "fr", "en")


class ModelUnavailable(Exception):
    """The model files are not installed or failed to load."""


class MediaRejected(Exception):
    """The media cannot be processed; the message is a stable error code."""


@dataclass(frozen=True, slots=True)
class Manifest:
    path: Path
    name: str
    data: dict[str, Any]


def read_manifest(directory: str) -> Manifest:
    path = get_settings().models_dir / directory
    try:
        data = json.loads((path / "manifest.json").read_text())
    except (OSError, ValueError) as exc:
        raise ModelUnavailable(f"{directory}: manifest.json missing") from exc
    return Manifest(path=path, name=str(data.get("name", directory)), data=data)


def _device() -> tuple[str, str]:
    settings = get_settings()
    device = settings.device
    if device == "auto":
        import ctranslate2

        device = "cuda" if ctranslate2.get_cuda_device_count() > 0 else "cpu"
    compute = settings.compute_type
    if compute == "auto":
        compute = "float16" if device == "cuda" else "int8"
    return device, compute


class _Lazy[T]:
    """Load a model once, on first use, from any thread."""

    def __init__(self, directory: str) -> None:
        self.directory = directory
        self._value: T | None = None
        self._lock = threading.Lock()

    def load(self) -> T:
        raise NotImplementedError

    def get(self) -> T:
        if self._value is None:
            with self._lock:
                if self._value is None:
                    self._value = self.load()
        return self._value

    def manifest_name(self) -> str | None:
        try:
            return read_manifest(self.directory).name
        except ModelUnavailable:
            return None


# ---------------------------------------------------------------- speech to text (FR-A-044)


@dataclass(frozen=True, slots=True)
class Transcript:
    text: str
    language: str
    language_probability: float
    duration_s: float
    segments: list[tuple[float, float, str]]


class Whisper(_Lazy[Any]):
    def load(self) -> Any:
        from faster_whisper import WhisperModel

        manifest = read_manifest(self.directory)
        device, compute = _device()
        try:
            return WhisperModel(
                str(manifest.path), device=device, compute_type=compute, cpu_threads=get_settings().cpu_threads
            )
        except Exception as exc:
            raise ModelUnavailable(f"whisper: {exc}") from exc

    def transcribe(self, audio_path: str, language: str | None) -> Transcript:
        from faster_whisper.audio import decode_audio

        settings = get_settings()
        model = self.get()
        sampling_rate = model.feature_extractor.sampling_rate
        try:
            audio = decode_audio(audio_path, sampling_rate=sampling_rate)
        except Exception as exc:  # PyAV raises many error types (some are ValueError) for bad input
            raise MediaRejected("media_undecodable") from exc
        if len(audio) / sampling_rate > settings.max_audio_s:
            raise MediaRejected("audio_too_long")
        options: dict[str, Any] = {
            "beam_size": settings.whisper_beam_size,
            "vad_filter": True,
            "condition_on_previous_text": False,
        }
        probability = 1.0
        if language is None:
            # Segments are decoded lazily: this call only runs language detection.
            _, info = model.transcribe(audio, **options)
            language, probability = info.language, float(info.language_probability)
            if language not in ALLOWED_SPEECH_LANGUAGES:
                # Tunisian dialect is sometimes detected as another language: keep the best of ar / fr / en.
                probabilities = dict(info.all_language_probs or [])
                language = max(ALLOWED_SPEECH_LANGUAGES, key=lambda code: probabilities.get(code, 0.0))
                probability = float(probabilities.get(language, 0.0))
        # The dialect vocabulary hint noticeably improves the spelling of Tunisian words.
        prompt = settings.whisper_prompt_ar if language == "ar" else None
        segments, info = model.transcribe(audio, language=language, initial_prompt=prompt, **options)
        parts = [(float(s.start), float(s.end), s.text.strip()) for s in segments]
        return Transcript(
            text=" ".join(p[2] for p in parts if p[2]).strip(),
            language=info.language,
            language_probability=probability,
            duration_s=float(info.duration),
            segments=parts,
        )


# ---------------------------------------------------------------- translation (FR-A-045)

_SENTENCE_END = re.compile(r"(?<=[.!?؟…])\s+|\n+")
_MAX_SOURCE_TOKENS = 400


class Translator(_Lazy[tuple[Any, Any, Any, str | None]]):
    """Opus-MT (Marian) converted to CTranslate2; sentencepiece models from the original repository."""

    def load(self) -> tuple[Any, Any, Any, str | None]:
        import ctranslate2
        import sentencepiece as spm

        manifest = read_manifest(self.directory)
        device, compute = _device()
        try:
            translator = ctranslate2.Translator(str(manifest.path), device=device, compute_type=compute)
            source = spm.SentencePieceProcessor(model_file=str(manifest.path / "source.spm"))
            target = spm.SentencePieceProcessor(model_file=str(manifest.path / "target.spm"))
        except Exception as exc:
            raise ModelUnavailable(f"{self.directory}: {exc}") from exc
        prefix = manifest.data.get("source_prefix")
        return translator, source, target, str(prefix) if prefix else None

    def translate(self, texts: list[str]) -> list[str]:
        translator, source, target, prefix = self.get()
        # Translate sentence by sentence (Marian is trained on sentences), then re-join per input text.
        pieces: list[list[str]] = []
        owners: list[int] = []
        for index, text in enumerate(texts):
            for sentence in split_sentences(text):
                tokens = source.encode(sentence, out_type=str)[:_MAX_SOURCE_TOKENS]
                pieces.append(([prefix] if prefix else []) + tokens + ["</s>"])
                owners.append(index)
        results = translator.translate_batch(pieces, beam_size=4, max_batch_size=16) if pieces else []
        joined: list[list[str]] = [[] for _ in texts]
        for owner, result in zip(owners, results, strict=True):
            joined[owner].append(target.decode(result.hypotheses[0]))
        return [" ".join(parts).strip() for parts in joined]


def split_sentences(text: str) -> list[str]:
    return [s.strip() for s in _SENTENCE_END.split(text) if s and s.strip()]


# ---------------------------------------------------------------- embeddings (grouping, semantic search)


class Embedder(_Lazy[tuple[Any, Any, str, int]]):
    """multilingual-e5 (XLM-RoBERTa encoder) converted to CTranslate2; mean pooling + L2 normalization."""

    def load(self) -> tuple[Any, Any, str, int]:
        import ctranslate2
        from tokenizers import Tokenizer

        manifest = read_manifest(self.directory)
        device, compute = _device()
        try:
            encoder = ctranslate2.Encoder(str(manifest.path), device=device, compute_type=compute)
            tokenizer = Tokenizer.from_file(str(manifest.path / "tokenizer.json"))
        except Exception as exc:
            raise ModelUnavailable(f"embed: {exc}") from exc
        tokenizer.enable_truncation(max_length=512)
        return encoder, tokenizer, str(manifest.data.get("prefix", "query: ")), int(manifest.data.get("dim", 768))

    def embed(self, texts: list[str]) -> np.ndarray:
        encoder, tokenizer, prefix, dim = self.get()
        encodings = tokenizer.encode_batch([prefix + t for t in texts])
        tokens = [e.tokens for e in encodings]
        output = encoder.forward_batch(tokens)
        hidden = np.array(output.last_hidden_state, dtype=np.float32)  # (batch, max_len, dim)
        return mean_pool(hidden, [len(t) for t in tokens], dim)


def mean_pool(hidden: np.ndarray, lengths: list[int], dim: int) -> np.ndarray:
    if hidden.shape[-1] != dim:
        raise ModelUnavailable(f"embed: model dimension {hidden.shape[-1]} != {dim}")
    mask = np.zeros(hidden.shape[:2], dtype=np.float32)
    for row, length in enumerate(lengths):
        mask[row, :length] = 1.0
    summed = (hidden * mask[..., None]).sum(axis=1)
    pooled = summed / np.maximum(mask.sum(axis=1, keepdims=True), 1.0)
    norms = np.linalg.norm(pooled, axis=1, keepdims=True)
    result: np.ndarray = pooled / np.maximum(norms, 1e-12)
    return result


whisper = Whisper("whisper")
translators = {"fr": Translator("opus-mt-fr-ar"), "en": Translator("opus-mt-en-ar")}
embedder = Embedder("embed")
