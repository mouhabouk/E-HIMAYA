"""Download, convert and check the local models of the AI service, then pull the language model into Ollama.

Run once per installation (Docker target "models", or CI). The runtime service never downloads anything:
the models live in AI_MODELS_DIR on our own servers (NFR-10, NFR-11).

    python models/fetch_models.py --profile prod --out /models --ollama http://ollama:11434

Profiles (docs/versions.md lists the models and their licences):
    prod  GPU server: Whisper large-v3, Opus-MT fr→ar and en→ar, multilingual-e5-base, Qwen3 8B
    cpu   CPU-only server: Whisper medium, same translation and embedding models, Qwen3 4B
    ci    automated tests: Whisper small, same translation and embedding models, Qwen3 1.7B
"""

import argparse
import json
import shutil
import sys
from pathlib import Path
from typing import Any

import httpx

PROFILES: dict[str, dict[str, str]] = {
    "prod": {"whisper": "Systran/faster-whisper-large-v3", "llm": "qwen3:8b"},
    "cpu": {"whisper": "Systran/faster-whisper-medium", "llm": "qwen3:4b"},
    "ci": {"whisper": "Systran/faster-whisper-small", "llm": "qwen3:1.7b"},
}
TRANSLATION = {"opus-mt-fr-ar": "Helsinki-NLP/opus-mt-fr-ar", "opus-mt-en-ar": "Helsinki-NLP/opus-mt-en-ar"}
EMBEDDING = "intfloat/multilingual-e5-base"
EMBEDDING_DIM = 768  # reports.report.embedding is vector(768)
# Only the PyTorch weights and tokenizer: the repo also ships ONNX/OpenVINO copies (several GB).
EMBEDDING_FILES = [
    "config.json",
    "model.safetensors",
    "sentencepiece.bpe.model",
    "special_tokens_map.json",
    "tokenizer.json",
    "tokenizer_config.json",
]
# Licences accepted for production use (NFR-10): permissive only.
ALLOWED_LICENSES = {"mit", "apache-2.0", "cc-by-4.0"}


def snapshot(repo: str, patterns: list[str] | None = None) -> tuple[Path, str, str]:
    from huggingface_hub import HfApi, snapshot_download

    info = HfApi().model_info(repo)
    license_ = str((info.card_data or {}).get("license", "unknown")).lower()
    if license_ not in ALLOWED_LICENSES:
        sys.exit(f"{repo}: licence {license_!r} is not in the accepted list {sorted(ALLOWED_LICENSES)}")
    path = snapshot_download(repo, revision=info.sha, allow_patterns=patterns)
    return Path(path), str(info.sha), license_


def write_manifest(target: Path, **data: Any) -> None:
    (target / "manifest.json").write_text(json.dumps(data, ensure_ascii=False, indent=2))
    print(f"✓ {target.name}: {data['source']}@{str(data['revision'])[:10]} ({data['license']})")


def installed(target: Path, source: str) -> bool:
    """Already prepared from the same source: keep it (re-run with --force to refresh)."""
    try:
        return FORCE is False and json.loads((target / "manifest.json").read_text()).get("source") == source
    except (OSError, ValueError):
        return False


FORCE = False


def fresh(target: Path) -> Path:
    if target.exists():
        shutil.rmtree(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    return target


def fetch_whisper(out: Path, repo: str) -> None:
    if installed(out / "whisper", repo):
        print(f"= whisper: {repo} already installed")
        return
    source, revision, license_ = snapshot(repo)
    target = fresh(out / "whisper")
    shutil.copytree(source, target)
    write_manifest(target, name=repo.split("/")[-1], source=repo, revision=revision, license=license_)


def fetch_translation(out: Path, name: str, repo: str) -> None:
    import ctranslate2
    import sentencepiece as spm
    from ctranslate2.converters import TransformersConverter
    from transformers import AutoTokenizer

    if installed(out / name, repo):
        print(f"= {name}: {repo} already installed")
        return
    source, revision, license_ = snapshot(repo)
    target = fresh(out / name)
    TransformersConverter(str(source)).convert(str(target), quantization="float16")
    for spm_file in ("source.spm", "target.spm"):
        shutil.copy(source / spm_file, target / spm_file)
    # Multi-target Opus-MT models need a target-language token (>>ara<<) at the start of the source.
    prefix = ">>ara<<" if ">>ara<<" in AutoTokenizer.from_pretrained(str(source)).get_vocab() else None

    # Check: a short French or English sentence must come out in Arabic script.
    sample = {"opus-mt-fr-ar": "Il y a un grand incendie dans la forêt.", "opus-mt-en-ar": "A big fire in the forest."}
    translator = ctranslate2.Translator(str(target), compute_type="int8")
    sp_source = spm.SentencePieceProcessor(model_file=str(target / "source.spm"))
    sp_target = spm.SentencePieceProcessor(model_file=str(target / "target.spm"))
    tokens = ([prefix] if prefix else []) + sp_source.encode(sample[name], out_type=str) + ["</s>"]
    result = sp_target.decode(translator.translate_batch([tokens])[0].hypotheses[0])
    if not any("؀" <= ch <= "ۿ" for ch in result):
        sys.exit(f"{name}: conversion check failed, output {result!r}")
    print(f"  {sample[name]} → {result}")
    write_manifest(
        target, name=repo.split("/")[-1], source=repo, revision=revision, license=license_, source_prefix=prefix
    )


def fetch_embedding(out: Path) -> None:
    import ctranslate2
    import numpy as np
    import torch
    from ctranslate2.converters import TransformersConverter
    from tokenizers import Tokenizer
    from transformers import AutoModel, AutoTokenizer

    if installed(out / "embed", EMBEDDING):
        print(f"= embed: {EMBEDDING} already installed")
        return
    source, revision, license_ = snapshot(EMBEDDING, EMBEDDING_FILES)
    target = fresh(out / "embed")
    TransformersConverter(str(source)).convert(str(target), quantization="float16")
    shutil.copy(source / "tokenizer.json", target / "tokenizer.json")

    # Check: the converted encoder must give the same sentence vectors as the reference implementation.
    sentences = ["query: حريق كبير في الغابة قرب الطريق", "query: Il y a une inondation dans le quartier."]
    tokenizer = AutoTokenizer.from_pretrained(str(source))
    model = AutoModel.from_pretrained(str(source)).eval()
    with torch.no_grad():
        batch = tokenizer(sentences, padding=True, return_tensors="pt")
        hidden = model(**batch).last_hidden_state
        mask = batch["attention_mask"].unsqueeze(-1).float()
        reference = torch.nn.functional.normalize((hidden * mask).sum(1) / mask.sum(1), dim=-1).numpy()
    fast = Tokenizer.from_file(str(target / "tokenizer.json"))
    tokens = [e.tokens for e in fast.encode_batch(sentences)]
    encoder = ctranslate2.Encoder(str(target), compute_type="float32")
    states = np.array(encoder.forward_batch(tokens).last_hidden_state, dtype=np.float32)
    masks = np.zeros(states.shape[:2], dtype=np.float32)
    for row, t in enumerate(tokens):
        masks[row, : len(t)] = 1
    pooled = (states * masks[..., None]).sum(1) / masks.sum(1, keepdims=True)
    pooled /= np.linalg.norm(pooled, axis=1, keepdims=True)
    cosine = (pooled * reference).sum(1)
    if pooled.shape[1] != EMBEDDING_DIM or cosine.min() < 0.99:
        sys.exit(f"embed: conversion check failed (dim {pooled.shape[1]}, cosine {cosine.tolist()})")
    print(f"  cosine with reference: {[round(float(c), 4) for c in cosine]}")
    write_manifest(
        target,
        name="multilingual-e5-base",
        source=EMBEDDING,
        revision=revision,
        license=license_,
        dim=EMBEDDING_DIM,
        prefix="query: ",
    )


def pull_llm(ollama: str, model: str, out: Path) -> None:
    with httpx.Client(timeout=httpx.Timeout(30, read=3600)) as client:
        response = client.post(f"{ollama}/api/pull", json={"model": model, "stream": False})
        if response.status_code != 200 or response.json().get("status") != "success":
            sys.exit(f"ollama pull {model} failed: {response.status_code} {response.text[:300]}")
        details = client.post(f"{ollama}/api/show", json={"model": model}).json()
    license_text = str(details.get("license", ""))[:200].replace("\n", " ")
    if "apache" not in license_text.lower():
        sys.exit(f"{model}: unexpected licence {license_text!r}")
    (out / "llm.json").write_text(json.dumps({"name": model, "license": "apache-2.0"}, indent=2))
    print(f"✓ llm: {model} (Apache-2.0)")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--profile", choices=sorted(PROFILES), default="prod")
    parser.add_argument("--out", type=Path, default=Path("/models"))
    parser.add_argument("--ollama", default=None, help="Ollama base URL; the language model is skipped when absent")
    parser.add_argument("--only", nargs="*", choices=["whisper", "translate", "embed", "llm"])
    parser.add_argument("--force", action="store_true", help="download and convert again even if installed")
    args = parser.parse_args()
    global FORCE
    FORCE = args.force
    profile = PROFILES[args.profile]
    wanted = set(args.only or ["whisper", "translate", "embed", "llm"])
    args.out.mkdir(parents=True, exist_ok=True)
    if "whisper" in wanted:
        fetch_whisper(args.out, profile["whisper"])
    if "translate" in wanted:
        for name, repo in TRANSLATION.items():
            fetch_translation(args.out, name, repo)
    if "embed" in wanted:
        fetch_embedding(args.out)
    if "llm" in wanted and args.ollama:
        pull_llm(args.ollama, profile["llm"], args.out)


if __name__ == "__main__":
    main()
