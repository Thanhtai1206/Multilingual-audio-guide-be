"""
Truy hồi văn bản (phần "R" trong RAG) bằng thuật toán BM25 - viết thuần Python.

Vì sao không dùng vector embedding như PRD? Embedding cần dịch vụ trả phí (Azure OpenAI).
BM25 là thuật toán xếp hạng từ khóa kinh điển (Elasticsearch dùng mặc định), miễn phí,
đủ tốt với kho tri thức nhỏ của 1 ngôi chùa. Khi có ngân sách có thể thay lớp này
bằng vector search mà ChatService không phải đổi.
"""

import math
import re
import unicodedata
from collections import Counter
from dataclasses import dataclass

STOPWORDS = {
    # tiếng Việt (đã bỏ dấu)
    "la",
    "va",
    "cua",
    "co",
    "cac",
    "nhung",
    "mot",
    "nay",
    "do",
    "o",
    "tai",
    "cho",
    "voi",
    "duoc",
    "khong",
    "gi",
    "nao",
    "the",
    "thi",
    "ma",
    "nhu",
    "toi",
    "ban",
    "minh",
    "em",
    "anh",
    "chi",
    "a",
    "oi",
    "nhe",
    "vay",
    "sao",
    "bao",
    "nhieu",
    "khi",
    "trong",
    "tren",
    "den",
    "tu",
    "ve",
    "hay",
    # tiếng Anh
    "is",
    "are",
    "an",
    "of",
    "to",
    "in",
    "and",
    "what",
    "where",
    "how",
    "when",
    "can",
    "i",
    "you",
    "it",
    "this",
    "that",
    "for",
    "on",
    "at",
    "be",
    "does",
}


def normalize(text: str) -> str:
    """Chữ thường + bỏ dấu tiếng Việt: 'Quan Thế Âm' -> 'quan the am' (khớp cả khi khách gõ không dấu)."""
    text = text.lower().replace("đ", "d")
    text = unicodedata.normalize("NFD", text)
    return "".join(ch for ch in text if unicodedata.category(ch) != "Mn")


def tokenize(text: str) -> list[str]:
    return [t for t in re.findall(r"\w+", normalize(text)) if len(t) > 1 and t not in STOPWORDS]


def split_sentences(text: str) -> list[str]:
    return [s.strip() for s in re.split(r"(?<=[.!?])\s+|\n+", text) if s.strip()]


@dataclass
class Document:
    id: str
    type: str
    title: str
    text: str


@dataclass
class SearchHit:
    document: Document
    score: float


class BM25Index:
    def __init__(self, documents: list[Document], k1: float = 1.5, b: float = 0.75):
        self.documents = documents
        self.k1, self.b = k1, b
        # Tiêu đề được lặp 2 lần để tăng trọng số
        self.tokens = [tokenize(f"{d.title} {d.title} {d.text}") for d in documents]
        self.avg_len = (sum(len(t) for t in self.tokens) / len(self.tokens)) if self.tokens else 0
        df: Counter = Counter()
        for toks in self.tokens:
            df.update(set(toks))
        n = len(documents)
        self.idf = {term: math.log(1 + (n - freq + 0.5) / (freq + 0.5)) for term, freq in df.items()}

    def search(self, query: str, top_k: int = 3) -> list[SearchHit]:
        terms = tokenize(query)
        hits = []
        for doc, toks in zip(self.documents, self.tokens, strict=True):
            if not toks:
                continue
            tf = Counter(toks)
            score = 0.0
            for term in terms:
                if term not in tf:
                    continue
                freq = tf[term]
                denom = freq + self.k1 * (1 - self.b + self.b * len(toks) / (self.avg_len or 1))
                score += self.idf.get(term, 0) * freq * (self.k1 + 1) / denom
            if score > 0:
                hits.append(SearchHit(doc, score))
        return sorted(hits, key=lambda h: h.score, reverse=True)[:top_k]


def best_sentences(text: str, query: str, limit: int = 2) -> str:
    """Trích các câu liên quan nhất tới câu hỏi (trả lời kiểu trích đoạn khi không có LLM)."""
    sentences = split_sentences(text)
    if not sentences:
        return text
    q = set(tokenize(query))
    scored = [(len(q & set(tokenize(s))), i, s) for i, s in enumerate(sentences)]
    top = sorted(scored, key=lambda x: (-x[0], x[1]))[:limit]
    return " ".join(s for _, _, s in sorted(top, key=lambda x: x[1]))
