"""Orchestrate retrieval and answer generation for one question."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from ..models import Course, Message
from .llm import generate_answer
from .retrieval import build_retrieval_query, retrieve_chunks

MAX_QUOTE_CHARS = 240


@dataclass(frozen=True)
class CitationData:
    """Citation values ready to persist."""

    rank: int
    chunk_id: int
    document_title: str
    page_number: int | None
    quote: str
    score: float


@dataclass(frozen=True)
class QAResult:
    """Answer and citation data returned by the QA service."""

    answer: str
    mode: str
    model_name: str
    latency_ms: int
    citations: list[CitationData]


def answer_question(
    course: Course,
    question: str,
    history: Sequence[Message],
) -> QAResult:
    """Retrieve course context and produce an answer with citations."""
    retrieval_query = build_retrieval_query(question, history)
    chunks = retrieve_chunks(course.id, retrieval_query)
    result = generate_answer(course.title, question, chunks, history)
    citations = [
        CitationData(
            rank=index,
            chunk_id=item.chunk.id,
            document_title=item.chunk.document.title,
            page_number=item.chunk.page_number,
            quote=" ".join(item.chunk.content.split())[:MAX_QUOTE_CHARS],
            score=round(item.score, 4),
        )
        for index, item in enumerate(chunks, start=1)
    ]
    return QAResult(
        answer=result.text,
        mode=result.mode,
        model_name=result.model_name,
        latency_ms=result.latency_ms,
        citations=citations,
    )
