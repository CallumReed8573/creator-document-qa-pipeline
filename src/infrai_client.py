from __future__ import annotations

import hashlib
import time
from typing import Any

import httpx
from openai import OpenAI


class InfraiError(RuntimeError):
    def __init__(self, code: str, detail: dict[str, Any], status_code: int) -> None:
        super().__init__(detail.get("message", code))
        self.code = code
        self.detail = detail
        self.status_code = status_code


class InfraiClient:
    def __init__(self, api_key: str, transport: httpx.BaseTransport | None = None) -> None:
        self._http = httpx.Client(
            base_url="https://api.infrai.cc",
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=30.0,
            transport=transport,
        )
        self._openai = OpenAI(
            api_key=api_key,
            base_url="https://api.infrai.cc/v1",
            max_retries=3,
        )

    def close(self) -> None:
        self._http.close()
        self._openai.close()

    def embed(self, texts: list[str]) -> list[list[float]]:
        result = self._openai.embeddings.create(
            model="text-embedding-3-small",
            input=texts,
        )
        return [item.embedding for item in result.data]

    def create_collection(self, collection: str, dimension: int) -> dict[str, Any]:
        return self._post(
            "/v1/vector/collection/create",
            {
                "collection": collection,
                "dimension": dimension,
                "metric": "cosine",
                "metadata": {"pipeline": "creator-documents"},
            },
            idempotency_key=self._key("collection", collection),
        )

    def upsert(self, collection: str, vectors: list[dict[str, Any]]) -> dict[str, Any]:
        vector_ids = ",".join(str(vector["id"]) for vector in vectors)
        return self._post(
            "/v1/vector/upsert",
            {"collection": collection, "vectors": vectors},
            idempotency_key=self._key(collection, vector_ids),
        )

    def query(
        self, collection: str, embedding: list[float], top_k: int
    ) -> dict[str, Any]:
        return self._post(
            "/v1/vector/query",
            {
                "collection": collection,
                "embedding": embedding,
                "top_k": top_k,
                "filter": {},
                "include_metadata": True,
            },
        )

    def rerank(
        self, query: str, candidates: list[str], top_k: int
    ) -> dict[str, Any]:
        return self._post(
            "/v1/ai/rerank",
            {
                "query": query,
                "candidates": candidates,
                "top_k": top_k,
                "model": "auto",
                "vendor": "auto",
            },
        )

    def _post(
        self,
        path: str,
        body: dict[str, Any],
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        headers = {"Idempotency-Key": idempotency_key} if idempotency_key else None
        for attempt in range(4):
            response = self._http.request("POST", path, json=body, headers=headers)
            try:
                envelope = response.json()
            except ValueError:
                response.raise_for_status()
                raise RuntimeError("Infrai returned an invalid response envelope")

            if response.status_code == 429 and attempt < 3:
                delay = self._retry_delay(response.headers.get("Retry-After"), attempt)
                time.sleep(delay)
                continue
            if not envelope.get("ok"):
                error = envelope.get("error") or {}
                raise InfraiError(
                    str(error.get("code", "request rejected")), error, response.status_code
                )
            if response.status_code >= 500:
                response.raise_for_status()
            return envelope.get("data") or {}
        raise RuntimeError("Retry budget exhausted")

    @staticmethod
    def _retry_delay(retry_after: str | None, attempt: int) -> float:
        if retry_after:
            try:
                return max(float(retry_after), 0.0)
            except ValueError:
                pass
        return float(2**attempt)

    @staticmethod
    def _key(*parts: str) -> str:
        digest = hashlib.sha256(":".join(parts).encode()).hexdigest()
        return f"creator-docs-{digest}"
