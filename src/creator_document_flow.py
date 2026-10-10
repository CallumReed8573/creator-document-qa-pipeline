from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from pydantic import BaseModel, Field


class DocumentRecord(BaseModel):
    document_id: str
    title: str
    text: str
    asset_id: str
    subscriber_tier: str
    processing_state: str


class QuestionRequest(BaseModel):
    question: str = Field(min_length=3)
    top_k: int = Field(default=3, ge=1, le=10)


class AnswerEvidence(BaseModel):
    document_id: str
    title: str
    excerpt: str
    asset_id: str
    subscriber_tier: str
    processing_state: str


class QuestionResponse(BaseModel):
    answer: str
    evidence: list[AnswerEvidence]


class SearchClient(Protocol):
    def embed(self, texts: list[str]) -> list[list[float]]:
        raise AssertionError("protocol method")

    def query(
        self, collection: str, embedding: list[float], top_k: int
    ) -> dict[str, Any]:
        raise AssertionError("protocol method")

    def rerank(
        self, query: str, candidates: list[str], top_k: int
    ) -> dict[str, Any]:
        raise AssertionError("protocol method")


@dataclass
class CreatorDocumentFlow:
    client: SearchClient
    collection: str

    def answer(self, request: QuestionRequest) -> QuestionResponse:
        query_vector = self.client.embed([request.question])[0]
        search_data = self.client.query(
            self.collection, query_vector, max(request.top_k * 3, request.top_k)
        )
        matches = search_data.get("matches", [])
        candidates = [str(match.get("metadata", {}).get("text", "")) for match in matches]
        candidates = [text for text in candidates if text]
        if not candidates:
            return QuestionResponse(
                answer="No matching processed creator document was found.", evidence=[]
            )

        reranked = self.client.rerank(request.question, candidates, request.top_k)
        selected = self._selected_texts(reranked, candidates, request.top_k)
        evidence = [self._evidence(text, matches) for text in selected]
        return QuestionResponse(
            answer=self._compose_answer(request.question, evidence), evidence=evidence
        )

    @staticmethod
    def _selected_texts(
        reranked: dict[str, Any], candidates: list[str], top_k: int
    ) -> list[str]:
        results = reranked.get("results", [])
        selected: list[str] = []
        for result in results[:top_k]:
            if isinstance(result.get("candidate"), str):
                selected.append(result["candidate"])
            elif isinstance(result.get("index"), int):
                selected.append(candidates[result["index"]])
        return selected or candidates[:top_k]

    @staticmethod
    def _evidence(text: str, matches: list[dict[str, Any]]) -> AnswerEvidence:
        metadata = next(
            (match.get("metadata", {}) for match in matches if match.get("metadata", {}).get("text") == text),
            {},
        )
        return AnswerEvidence(
            document_id=str(metadata.get("document_id", "unknown")),
            title=str(metadata.get("title", "Untitled")),
            excerpt=text,
            asset_id=str(metadata.get("asset_id", "unknown")),
            subscriber_tier=str(metadata.get("subscriber_tier", "unknown")),
            processing_state=str(metadata.get("processing_state", "unknown")),
        )

    @staticmethod
    def _compose_answer(question: str, evidence: list[AnswerEvidence]) -> str:
        lead = evidence[0]
        return f"For '{question}', {lead.excerpt} (source: {lead.title})."
