import re
from blob_reader import read_log_from_blob

# from datetime import datetime

LOG_PATTERN = r"(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) (\w+) (\d+\.\d+\.\d+\.\d+) (\w+) (\S+) (\d+) (\d+)ms"


def parse_log_line(line: str) -> dict | None:
    match = re.match(LOG_PATTERN, line)

    if not match:
        return None  # line doesn't match the format - skip it

    return {
        "timestamp": match.group(1),
        "level": match.group(2),
        "ip": match.group(3),
        "method": match.group(4),
        "endpoint": match.group(5),
        "status": int(match.group(6)),
        "latency_ms": int(match.group(7)),
    }


def parse_log_file(text: str) -> list[dict]:
    result = []
    for line in text.splitlines():
        parsed = parse_log_line(line.strip())
        if parsed:
            result.append(parsed)
    return result


if __name__ == "__main__":
    log_text = read_log_from_blob("test.log")
    entries = parse_log_file(log_text)
    print(f"Parsed {len(entries)} lines")
    for entry in entries:
        print(entry)
