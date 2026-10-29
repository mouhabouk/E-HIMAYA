"""A small text classifier learnt locally from the report texts: character n-grams, TF-IDF, logistic regression.

Character n-grams of the normalised words (moderation.normalize: Arabic letter variants, diacritics, case, letters
repeated for emphasis) read Tunisian Derja in Arabic and in Latin script (Arabizi), French and English alike, with no
word list and no tokenizer per language. The vocabulary, the IDF weights and the coefficients are stored as plain
numbers (no pickle, nothing executable, as coastal/shadow.py) and applied in pure Python, so a prediction needs
neither scikit-learn nor numpy; scikit-learn is used only to fit.
"""

import math
from collections import Counter
from collections.abc import Iterable, Sequence
from typing import Any

from app.modules.moderation.normalize import tokens

ALGORITHM = "char n-grams 2-4 + TF-IDF + scikit-learn LogisticRegression"
NGRAMS = (2, 3, 4)
MAX_FEATURES = 6000
MIN_DOCUMENTS = 2


def ngrams(text: str) -> Counter[str]:
    """Character n-grams of each normalised word, the word padded with spaces (" نار " → " ن", "نا", "ار", "ر ")."""
    grams: Counter[str] = Counter()
    for word in tokens(text):
        padded = f" {word} "
        for n in NGRAMS:
            grams.update(padded[i : i + n] for i in range(len(padded) - n + 1))
    return grams


def vocabulary(texts: Iterable[str]) -> tuple[list[str], list[float]]:
    """The MAX_FEATURES n-grams found in the most texts (at least MIN_DOCUMENTS), with their smoothed IDF."""
    df: Counter[str] = Counter()
    count = 0
    for text in texts:
        count += 1
        df.update(set(ngrams(text)))
    kept = sorted((g for g, n in df.items() if n >= MIN_DOCUMENTS), key=lambda g: (-df[g], g))[:MAX_FEATURES]
    return kept, [round(math.log((1 + count) / (1 + df[g])) + 1.0, 6) for g in kept]


def vector(text: str, index: dict[str, int], idf: Sequence[float]) -> dict[int, float]:
    """Sublinear TF × IDF, L2-normalised; only the n-grams of the vocabulary."""
    weights = {index[g]: (1.0 + math.log(c)) * idf[index[g]] for g, c in ngrams(text).items() if g in index}
    norm = math.sqrt(sum(w * w for w in weights.values())) or 1.0
    return {i: w / norm for i, w in weights.items()}


def fit(texts: Sequence[str], labels: Sequence[str], weights: Sequence[float]) -> dict[str, Any]:
    """Fits the classifier; returns its parameters as plain numbers."""
    from scipy.sparse import csr_matrix
    from sklearn.linear_model import LogisticRegression

    vocab, idf = vocabulary(texts)
    index = {g: i for i, g in enumerate(vocab)}
    rows, cols, values = [], [], []
    for r, text in enumerate(texts):
        for c, v in vector(text, index, idf).items():
            rows.append(r)
            cols.append(c)
            values.append(v)
    matrix = csr_matrix((values, (rows, cols)), shape=(len(texts), len(vocab)))
    model = LogisticRegression(max_iter=2000, C=4.0, class_weight="balanced")
    model.fit(matrix, list(labels), sample_weight=list(weights))
    classes = [str(c) for c in model.classes_]
    coef = model.coef_.tolist()
    intercept = model.intercept_.tolist()
    if len(classes) == 2:
        # scikit-learn keeps one row for two classes (the second); store both so prediction is one code path.
        coef = [[-c for c in coef[0]], coef[0]]
        intercept = [-intercept[0], intercept[0]]
    return {
        "vocabulary": vocab,
        "idf": idf,
        "classes": classes,
        "coef": [[round(float(c), 5) for c in row] for row in coef],
        "intercept": [round(float(b), 5) for b in intercept],
    }


class Classifier:
    """A stored classifier ready to apply (the n-gram index is built once)."""

    def __init__(self, params: dict[str, Any]) -> None:
        self.classes: list[str] = list(params["classes"])
        self._idf: list[float] = list(params["idf"])
        self._coef: list[list[float]] = params["coef"]
        self._intercept: list[float] = params["intercept"]
        self._index = {g: i for i, g in enumerate(params["vocabulary"])}

    def probabilities(self, text: str) -> dict[str, float]:
        """Probability of each class for ``text`` (softmax of the linear scores)."""
        x = vector(text, self._index, self._idf)
        linear = [b + sum(row[i] * v for i, v in x.items()) for row, b in zip(self._coef, self._intercept, strict=True)]
        top = max(linear)
        exps = [math.exp(s - top) for s in linear]
        total = sum(exps)
        return {c: e / total for c, e in zip(self.classes, exps, strict=True)}

    def predict(self, text: str) -> str:
        p = self.probabilities(text)
        return max(p, key=lambda c: p[c])


def scores(truth: Sequence[str], predicted: Sequence[str]) -> dict[str, Any]:
    """Accuracy, macro F1 and per-class precision, recall and F1 (the recall of a danger class is its catch rate)."""
    classes = sorted(set(truth) | set(predicted))
    per_class: dict[str, dict[str, float | int]] = {}
    for c in classes:
        tp = sum(t == c and p == c for t, p in zip(truth, predicted, strict=True))
        fp = sum(t != c and p == c for t, p in zip(truth, predicted, strict=True))
        fn = sum(t == c and p != c for t, p in zip(truth, predicted, strict=True))
        precision = tp / (tp + fp) if tp + fp else 0.0
        recall = tp / (tp + fn) if tp + fn else 0.0
        f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
        per_class[c] = {
            "support": tp + fn,
            "precision": round(precision, 4),
            "recall": round(recall, 4),
            "f1": round(f1, 4),
        }
    present = [c for c in classes if per_class[c]["support"]]
    return {
        "n": len(truth),
        "accuracy": round(sum(t == p for t, p in zip(truth, predicted, strict=True)) / len(truth), 4) if truth else 0.0,
        "macro_f1": round(sum(float(per_class[c]["f1"]) for c in present) / len(present), 4) if present else 0.0,
        "classes": per_class,
    }
