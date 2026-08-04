import os

from azure.core.credentials import AzureKeyCredential
from azure.search.documents import SearchClient
from azure.search.documents.models import VectorizedQuery
from dotenv import load_dotenv

from embedder import generate_embedding

load_dotenv()

SELECT_FIELDS = ["timestamp", "level", "ip", "method", "endpoint", "status", "latency_ms"]


def get_search_client() -> SearchClient:
    return SearchClient(
        endpoint=os.getenv("AZURE_SEARCH_ENDPOINT"),
        index_name=os.getenv("AZURE_SEARCH_INDEX"),
        credential=AzureKeyCredential(os.getenv("AZURE_SEARCH_KEY")),
    )


def search_by_vector(vector: list[float], top_k: int = 3) -> list[dict]:
    vector_query = VectorizedQuery(
        vector=vector,
        k_nearest_neighbors=top_k,
        fields="embedding",
    )

    client = get_search_client()
    results = client.search(
        search_text=None,
        vector_queries=[vector_query],
        select=SELECT_FIELDS,
    )

    return [dict(r) for r in results]


def search_similar(log_text: str, top_k: int = 3) -> list[dict]:
    """Search by raw text - one embedding for the whole string."""
    return search_by_vector(generate_embedding(log_text), top_k=top_k)


def is_suspicious_record(record: dict) -> bool:
    return record.get("level") == "WARN" or record.get("status", 0) >= 400


def _record_key(record: dict) -> tuple:
    return (
        record.get("timestamp"),
        record.get("ip"),
        record.get("endpoint"),
        record.get("status"),
    )


def search_similar_for_entries(
    entries: list[dict],
    top_k: int = 3,
    only_suspicious: bool = True,
) -> list[dict]:
    """
    Search per log line using precomputed embeddings from embed_records().
    Matches index granularity: one record = one vector query.
    """
    candidates = [e for e in entries if is_suspicious_record(e)] if only_suspicious else entries
    if not candidates:
        return []

    seen: set[tuple] = set()
    results: list[dict] = []

    for entry in candidates:
        embedding = entry.get("embedding")
        if not embedding:
            continue

        for hit in search_by_vector(embedding, top_k=top_k):
            key = _record_key(hit)
            if key not in seen:
                seen.add(key)
                results.append(hit)

    return results


if __name__ == "__main__":
    from blob_reader import read_log_from_blob
    from embedder import embed_records
    from parser import parse_log_file

    entries = parse_log_file(read_log_from_blob("test.log"))
    embedded = embed_records(entries)

    print("Per-record search (suspicious only):\n")
    results = search_similar_for_entries(embedded, top_k=3)
    print(f"Found {len(results)} similar records:")
    for r in results:
        print(f"  {r['timestamp']} {r['level']} {r['ip']} {r['endpoint']} {r['status']}")
