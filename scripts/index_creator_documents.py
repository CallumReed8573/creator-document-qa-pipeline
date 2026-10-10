from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.creator_document_flow import DocumentRecord
from src.infrai_client import InfraiClient


def main() -> None:
    parser = argparse.ArgumentParser(description="Index processed creator documents")
    parser.add_argument("input", type=Path)
    parser.add_argument("--collection", default="creator-operations")
    args = parser.parse_args()

    records = [DocumentRecord.model_validate(item) for item in json.loads(args.input.read_text())]
    client = InfraiClient(os.environ["INFRAI_API_KEY"])
    try:
        embeddings = client.embed([record.text for record in records])
        client.create_collection(args.collection, len(embeddings[0]))
        vectors = [
            {
                "id": record.document_id,
                "values": embedding,
                "metadata": record.model_dump(),
            }
            for record, embedding in zip(records, embeddings, strict=True)
        ]
        client.upsert(args.collection, vectors)
    finally:
        client.close()
    print(f"Indexed {len(records)} creator documents into {args.collection}.")


if __name__ == "__main__":
    main()
