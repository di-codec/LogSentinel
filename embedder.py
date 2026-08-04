from azure_openai import get_azure_openai_client, require_env

client = get_azure_openai_client()


def record_to_text(record: dict) -> str:
    return (
        f"{record['timestamp']} {record['level']} {record['ip']} {record['method']} "
        f"{record['endpoint']} {record['status']} {record['latency_ms']}ms"
    )


def generate_embedding(text: str) -> list[float]:
    deployment = require_env("AZURE_OPENAI_EMBEDDING_DEPLOYMENT")
    response = client.embeddings.create(model=deployment, input=text)
    return response.data[0].embedding


def embed_records(records: list[dict]) -> list[dict]:
    if not records:
        return []

    deployment = require_env("AZURE_OPENAI_EMBEDDING_DEPLOYMENT")
    texts = [record_to_text(record) for record in records]
    response = client.embeddings.create(model=deployment, input=texts)

    embeddings_by_index = {item.index: item.embedding for item in response.data}
    return [
        {**record, "embedding": embeddings_by_index[index]}
        for index, record in enumerate(records)
    ]


if __name__ == "__main__":
    from blob_reader import read_log_from_blob
    from parser import parse_log_file

    entries = parse_log_file(read_log_from_blob("test.log"))
    embedded = embed_records(entries)

    print(f"Embedded {len(embedded)} records\n")
    for record in embedded:
        print(record_to_text(record), "→", len(record["embedding"]), "dims")
