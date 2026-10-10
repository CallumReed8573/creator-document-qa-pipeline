from src.creator_document_flow import CreatorDocumentFlow, QuestionRequest


class FakeSearchClient:
    def embed(self, texts: list[str]) -> list[list[float]]:
        assert texts == ["Which asset goes to annual subscribers?"]
        return [[0.1, 0.2, 0.3]]

    def query(self, collection: str, embedding: list[float], top_k: int) -> dict:
        assert collection == "creator-operations"
        assert embedding == [0.1, 0.2, 0.3]
        assert top_k == 6
        return {
            "matches": [
                {
                    "metadata": {
                        "document_id": "processing-208",
                        "title": "Transcript processing run",
                        "text": "Episode 208 was marked processed.",
                        "asset_id": "episode-208-transcript",
                        "subscriber_tier": "all",
                        "processing_state": "processed",
                    }
                },
                {
                    "metadata": {
                        "document_id": "delivery-1042",
                        "title": "September asset delivery",
                        "text": "Annual subscribers receive asset dl-1042.",
                        "asset_id": "dl-1042",
                        "subscriber_tier": "annual",
                        "processing_state": "processed",
                    }
                },
            ]
        }

    def rerank(self, query: str, candidates: list[str], top_k: int) -> dict:
        assert top_k == 2
        return {"results": [{"index": 1}, {"index": 0}]}


def test_answer_prefers_the_delivery_policy_after_reranking() -> None:
    flow = CreatorDocumentFlow(FakeSearchClient(), "creator-operations")

    result = flow.answer(
        QuestionRequest(question="Which asset goes to annual subscribers?", top_k=2)
    )

    assert result.evidence[0].asset_id == "dl-1042"
    assert result.evidence[0].subscriber_tier == "annual"
    assert result.evidence[0].processing_state == "processed"
    assert "Annual subscribers receive asset dl-1042" in result.answer

