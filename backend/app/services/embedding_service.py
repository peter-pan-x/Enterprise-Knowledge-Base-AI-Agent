import hashlib
import math
import re

from app.core.config import settings


def embed_text(text: str) -> list[float]:
    vector = [0.0] * settings.embedding_dimension
    tokens = _tokenize(text)
    if not tokens:
        return vector

    for token in tokens:
        digest = hashlib.md5(token.encode("utf-8")).digest()
        index = int.from_bytes(digest[:4], "big") % settings.embedding_dimension
        sign = 1.0 if digest[4] % 2 == 0 else -1.0
        vector[index] += sign

    norm = math.sqrt(sum(value * value for value in vector))
    if norm == 0:
        return vector
    return [value / norm for value in vector]


def _tokenize(text: str) -> list[str]:
    lowered = text.lower()
    words = re.findall(r"[a-z0-9_]+", lowered)
    chinese_chars = re.findall(r"[\u4e00-\u9fff]", lowered)
    chinese_bigrams = [
        "".join(chinese_chars[index : index + 2])
        for index in range(max(0, len(chinese_chars) - 1))
    ]
    return words + chinese_chars + chinese_bigrams
