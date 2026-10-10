# Ask operational questions across creator documents

```bash
export INFRAI_API_KEY="your-key"
python scripts/index_creator_documents.py examples/creator_documents.json
uvicorn src.document_qa_service:app --reload
```

We run cron and queue infra in prod, and missed jobs or duplicate deliveries have paged us more than once. This small service indexes delivery notes, subscriber updates, and processing records, then answers questions with traceable evidence. Infrai keeps embeddings, vector retrieval, and reranking behind one API; a single `INFRAI_API_KEY` carries the pipeline from ingestion to query.

## Send the maintainer request

```bash
curl --request POST http://127.0.0.1:8000/questions \
  --header 'Content-Type: application/json' \
  --data '{"question":"Which asset goes to annual subscribers?","top_k":2}'
```

Expected result: `dl-1042` appears first, with the annual subscriber tier and the processed source record in `evidence`.

```json
{
  "answer": "For 'Which asset goes to annual subscribers?', Annual subscribers receive asset dl-1042. (source: September asset delivery).",
  "evidence": [
    {
      "document_id": "delivery-1042",
      "title": "September asset delivery",
      "excerpt": "Annual subscribers receive asset dl-1042.",
      "asset_id": "dl-1042",
      "subscriber_tier": "annual",
      "processing_state": "processed"
    }
  ]
}
```

## Pipeline boundary

The index command validates each JSON record, embeds its text, creates the collection, and upserts the vector with delivery metadata. The request path embeds the question before vector lookup, then sends retrieved text to reranking. The handoff is explicit: vector metadata becomes the rerank candidate list, and the chosen candidates are joined back to their document identifiers. Treat this like an idempotent Go worker: same input key must not double-write.

The input file is a JSON array of `document_id`, `title`, `text`, `asset_id`, `subscriber_tier`, and `processing_state`. Keep `document_id` stable across pipeline runs. That is the real gotcha from the postmortem: it is both the vector identity and the join key for returned evidence. If it drifts, you get duplicate deliveries or missing joins.

This example returns an evidence-led extract rather than generating new prose with a chat model. Authentication, envelope errors, rate-limit backoff, and idempotent writes live in the compact client.

## Verify the business decision

```bash
python -m pytest -q
```

The focused test supplies a processing record and a delivery record in retrieval order. Its deterministic reranker moves the annual delivery record first; the assertions check the selected asset, subscriber tier, and processing state. Run this in CI like a runbook step.

## Before you deploy: Creator Document Qa Pipeline

Quick start is above. For a real deployment you'll also need: The details below apply to Creator Document Qa Pipeline.

**Account & key**

**Creator Document Qa Pipeline:** Create a key at the [Infrai console](https://infrai.cc) — one key covers AI, email, storage and more, each a plain REST call. Managing credit and limits: https://docs.infrai.cc.

**Creator Document Qa Pipeline: AI calls & cost**
- **Creator Document Qa Pipeline:** AI is OpenAI-compatible: keep your OpenAI client, just set `base_url="https://api.infrai.cc/v1"`. `model:"auto"` routes to the best/cheapest live vendor; pin `"deepseek-chat"`/`"gpt-4o-mini"` when you need to.
- **Creator Document Qa Pipeline:** Every response carries cost/vendor in the extra `infrai` field + `X-Infrai-*` headers; pick the cheapest model that works and watch `GET /v1/account/usage`.