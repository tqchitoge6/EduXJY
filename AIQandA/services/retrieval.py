"""Hybrid retrieval over course document chunks."""

from __future__ import annotations

import math
import re
from collections import Counter
from dataclasses import dataclass
from typing import Iterable, Sequence

from django.conf import settings

from ..models import DocumentChunk, KnowledgeDocument, Message
from .embeddings import embed_query

CHINESE_PATTERN = re.compile(r"[\u4e00-\u9fff]+")
WORD_PATTERN = re.compile(r"[a-z0-9]+")
MIN_SCORE = 0.02


@dataclass(frozen=True)
class RetrievedChunk:
    """A chunk with its retrieval score."""

    chunk: DocumentChunk
    score: float


def tokenize(text: str) -> list[str]:
    """Tokenize Chinese with character bigrams and English with words."""
    lowered = text.lower()
    tokens = WORD_PATTERN.findall(lowered)
    for sequence in CHINESE_PATTERN.findall(lowered):
        if len(sequence) == 1:
            tokens.append(sequence)
        else:
            tokens.extend(sequence[index : index + 2] for index in range(len(sequence) - 1))
    return tokens


def lexical_similarity(query_tokens: Sequence[str], text: str) -> float:
    """Return a cosine-like TF similarity in the range [0, 1]."""
    if not query_tokens:
        return 0.0
    document_tokens = tokenize(text)
    if not document_tokens:
        return 0.0
    query_counts = Counter(query_tokens)
    document_counts = Counter(document_tokens)
    numerator = sum(count * document_counts.get(token, 0) for token, count in query_counts.items())
    if numerator == 0:
        return 0.0
    query_norm = math.sqrt(sum(count * count for count in query_counts.values()))
    document_norm = math.sqrt(sum(count * count for count in document_counts.values()))
    if query_norm == 0 or document_norm == 0:
        return 0.0
    return min(numerator / (query_norm * document_norm), 1.0)


def embedding_similarity(left: Sequence[float], right: Sequence[float]) -> float:
    """Return cosine similarity for two vectors, clamped to [0, 1]."""
    if not left or not right or len(left) != len(right):
        return 0.0
    dot = sum(a * b for a, b in zip(left, right))
    left_norm = math.sqrt(sum(value * value for value in left))
    right_norm = math.sqrt(sum(value * value for value in right))
    if left_norm == 0 or right_norm == 0:
        return 0.0
    return max(0.0, min(dot / (left_norm * right_norm), 1.0))


def build_retrieval_query(question: str, history: Iterable[Message]) -> str:
    """Add the previous user turn for short follow-up questions."""
    previous_questions = [
        message.content
        for message in history
        if message.role == Message.Role.USER and message.content.strip()
    ]
    if previous_questions and len(question.strip()) < 18:
        return f"{previous_questions[-1]} {question}"
    return question


def retrieve_chunks(
    course_id: int,
    query: str,
    limit: int | None = None,
) -> list[RetrievedChunk]:
    """Retrieve the most relevant ready chunks for one course."""
    top_k = limit or settings.AI_TOP_K
    query = query.strip()
    if not query:
        return []

    chunks = list(
        DocumentChunk.objects.filter(
            document__course_id=course_id,
            document__status=KnowledgeDocument.Status.READY,
        ).select_related("document")
    )
    if not chunks:
        return []

    query_tokens = tokenize(query)
    query_embedding = None
    if settings.AI_EMBEDDING_MODEL and settings.AI_API_KEY:
        query_embedding = embed_query(query)

    scored: list[RetrievedChunk] = []
    for chunk in chunks:
        lexical = lexical_similarity(query_tokens, chunk.content)
        vector = 0.0
        if query_embedding and chunk.embedding:
            vector = embedding_similarity(query_embedding, chunk.embedding)
        if query_embedding and chunk.embedding:
            score = (0.65 * vector) + (0.35 * lexical)
        else:
            score = lexical
        if score > 0:
            scored.append(RetrievedChunk(chunk=chunk, score=score))

    scored.sort(key=lambda item: (-item.score, item.chunk.document_id, item.chunk.chunk_index))
    if not scored or scored[0].score < MIN_SCORE:
        return []
    return scored[:top_k]
