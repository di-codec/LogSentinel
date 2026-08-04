from dotenv import load_dotenv
from blob_reader import read_log_from_blob

from azure_openai import get_azure_openai_client, require_env
from search import search_similar, search_similar_for_entries

load_dotenv()
SYSTEM_PROMPT = (
    # "You are a cybersecurity expert. Analyze these logs and identify "
    # "anomalies, suspicious patterns, and potential security threats. "
    # "For each finding explain what you found, why it's suspicious, "
    # "and what action to take."
    "You are a cybersecurity expert analyzing server logs. "
    "Identify only suspicious patterns or anomalies - ignore normal traffic. "
    "For each finding, respond in this exact compact format:\n\n"
    "**[Severity: High/Medium/Low] Short title**\n"
    "- IP/Source: ...\n"
    "- Pattern: one sentence, what happened\n"
    "- Risk: one sentence, why it's suspicious\n"
    "- Action: one short, concrete recommendation\n\n"
    "Keep each finding under 4 lines total. No long paragraphs, "
    "no introductions, no summaries. If nothing suspicious is found, "
    "just say 'No anomalies detected.'"
)


def analyze_logs(log_text: str, embedded_entries: list[dict] | None = None) -> str:
    client = get_azure_openai_client()

    if embedded_entries is not None:
        similar = search_similar_for_entries(embedded_entries, top_k=3)
    else:
        similar = search_similar(log_text, top_k=3)
    
    context = ""
    if similar:
        context = "\n\nSimilar patterns from history:\n"
        for r in similar:
            context += f"- {r['timestamp']} {r['level']} {r['ip']} {r['endpoint']} {r['status']}\n"

    response = client.chat.completions.create(
        model=require_env("AZURE_OPENAI_DEPLOYMENT"),
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"Analyze these logs:\n\n{log_text}{context}"},
        ],
    )
    return response.choices[0].message.content


if __name__ == "__main__":
    logs = read_log_from_blob("test.log")  # reading from Blob

    print("Analyzing logs...\n")
    result = analyze_logs(logs)
    print(result)