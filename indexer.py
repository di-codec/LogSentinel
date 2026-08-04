import os
from azure.search.documents import SearchClient
from azure.core.credentials import AzureKeyCredential
from dotenv import load_dotenv

load_dotenv()


def get_search_client() -> SearchClient:
    return SearchClient(
        endpoint=os.getenv("AZURE_SEARCH_ENDPOINT"),
        index_name=os.getenv("AZURE_SEARCH_INDEX"),
        credential=AzureKeyCredential(os.getenv("AZURE_SEARCH_KEY"))
    )


def upload_records(records: list[dict]) -> None:
    client = get_search_client()

    documents = []
    for i, record in enumerate(records):
        doc = {**record, "id": str(i)}
        # Azure Search: Edm.DateTimeOffset requires ISO 8601 with a timezone offset
        ts = doc["timestamp"]
        if isinstance(ts, str) and "T" not in ts:
            doc["timestamp"] = ts.replace(" ", "T") + "Z"
        documents.append(doc)

    result = client.upload_documents(documents=documents)
    failed = [r for r in result if not r.succeeded]
    if failed:
        raise RuntimeError(f"Failed to upload {len(failed)} document(s): {failed}")


if __name__ == "__main__":
    from parser import parse_log_file
    from blob_reader import read_log_from_blob
    from embedder import embed_records

    entries = parse_log_file(read_log_from_blob("test.log"))
    embedded = embed_records(entries)
    
    print(f"Uploading {len(embedded)} records to Azure Search...")
    upload_records(embedded)
    print("Done!")