from __future__ import annotations

import os
from functools import lru_cache

from fastapi import Depends, FastAPI, HTTPException

from .creator_document_flow import CreatorDocumentFlow, QuestionRequest, QuestionResponse
from .infrai_client import InfraiClient, InfraiError

app = FastAPI(title="Creator document Q&A")


@lru_cache
def get_flow() -> CreatorDocumentFlow:
    api_key = os.environ["INFRAI_API_KEY"]
    collection = os.environ.get("INFRAI_COLLECTION", "creator-operations")
    return CreatorDocumentFlow(InfraiClient(api_key), collection)


@app.post("/questions", response_model=QuestionResponse)
def answer_question(
    request: QuestionRequest, flow: CreatorDocumentFlow = Depends(get_flow)
) -> QuestionResponse:
    try:
        return flow.answer(request)
    except InfraiError as exc:
        status = exc.status_code if 400 <= exc.status_code < 500 else 502
        raise HTTPException(status_code=status, detail=exc.detail) from exc

