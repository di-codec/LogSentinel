
░█░░░█▀█░█▀▀░█▀▀░█▀▀░█▀█░▀█▀░▀█▀░█▀█░█▀▀░█░░                                        
░█░░░█░█░█░█░▀▀█░█▀▀░█░█░░█░░░█░░█░█░█▀▀░█░░                                        
░▀▀▀░▀▀▀░▀▀▀░▀▀▀░▀▀▀░▀░▀░░▀░░▀▀▀░▀░▀░▀▀▀░▀▀▀
                                                  

<img alt="LogSentinel logo" align="right" src="./dashboard/public/favicon.png"  width="112" >

**AI-powered log anomaly detection with vector search and plain-language security analysis.**

LogSentinel ingests HTTP access logs, structures them into searchable records, indexes them in Azure AI Search, retrieves similar historical patterns via vector similarity, and uses Azure OpenAI to explain what looks suspicious and what to do about it. A React dashboard lets security analysts upload a `.log` file and get a readable report - no curl, no Swagger, no SIEM console required.

Built as a hands-on Azure AI engineering project; designed to read like a real product, not a tutorial walkthrough.

---

> **Design decisions, tradeoffs, and deployment lessons:** see [DESIGN_NOTES.md](DESIGN_NOTES.md).

---

## Why LogSentinel?

Traditional SIEM and rule-based alerting answer *"did this match a rule?"* - often with noisy alerts and little context. LogSentinel takes a different angle:

| Traditional SIEM | LogSentinel |
|------------------|-------------|
| Fixed rules and thresholds | LLM interprets patterns in context |
| Alert = one line in a queue | Finding = explanation + risk + recommended action |
| Historical correlation requires manual queries | Vector search surfaces similar past events automatically |
| Analyst needs query language fluency | Analyst uploads a file and reads markdown output |

LogSentinel does not replace a production SIEM. It demonstrates how **structured parsing + embeddings + retrieval-augmented generation (RAG)** can augment analyst workflows with explainable, narrative findings.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         React Dashboard (:3000)                         │
│              Login → Upload .log → Loading state → Markdown report      │
└─────────────────────────────────┬───────────────────────────────────────┘
                                  │ POST /analyze  (JWT or API key)
                                  ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                          FastAPI Backend (:8000)                        │
│  api.py  →  security (auth, rate limit, upload validation)              │
└─────────────────────────────────┬───────────────────────────────────────┘
                                  │
          ┌───────────────────────┼───────────────────────┐
          ▼                       ▼                       ▼
    parser.py              embedder.py              indexer.py
  (regex → dicts)    (Azure OpenAI embeddings)   (Azure AI Search upload)
          │                       │                       │
          └───────────────────────┼───────────────────────┘
                                  ▼
                            search.py
              (per-record vector search on WARN / 4xx lines)
                                  │
                                  ▼
                             main.py
           (GPT analysis + similar-pattern context → markdown report)
                                  │
                                  ▼
                         JSON response → Dashboard

  Optional path (CLI / scripts):
  blob_reader.py  →  Azure Blob Storage  →  same pipeline
```

**Request flow (dashboard):**

1. Analyst signs in; dashboard receives a JWT session token.
2. `.log` file is uploaded via `multipart/form-data`.
3. Each line is parsed into structured fields (timestamp, level, IP, method, endpoint, status, latency).
4. Records are embedded in batch (`text-embedding-3-small`) and indexed in Azure AI Search.
5. Suspicious lines (`WARN` or HTTP ≥ 400) trigger per-record similarity search against the vector index.
6. GPT receives the raw log text plus any matching historical patterns and returns compact markdown findings.
7. Dashboard renders the analysis with `react-markdown` and displays processing metrics.

---

## Tech Stack

| Layer | Technology |
|-------|------------|
| Backend | Python 3, FastAPI, Uvicorn |
| Frontend | React 19, Vite, react-markdown |
| LLM | Azure OpenAI - `gpt-4.1-mini` |
| Embeddings | Azure OpenAI - `text-embedding-3-small` (1536 dims) |
| Vector store | Azure AI Search |
| Object storage | Azure Blob Storage (CLI / script ingestion) |
| Parsing | Regex-based HTTP access log parser |
| Auth | JWT sessions (dashboard), API key (automation), rate limiting |

---

## Project Structure

```
Logsentinel/
├── api.py              # FastAPI app: /analyze, /auth/login, /health
├── main.py             # GPT analysis orchestration and system prompt
├── parser.py           # Regex parser: log lines → structured dicts
├── embedder.py         # Record → text → Azure OpenAI embedding vectors
├── indexer.py          # Upload embedded records to Azure AI Search
├── search.py           # Vector similarity search (per suspicious record)
├── blob_reader.py      # Read log files from Azure Blob Storage
├── azure_openai.py     # Shared Azure OpenAI client configuration
├── security.py         # Auth, JWT, rate limits, upload validation, CORS helpers
├── requirements.txt    # Python dependencies
├── .env.example        # Environment variable template
├── sample_logs/        # Example input logs and sample reports
└── dashboard/          # React frontend
    └── src/
        ├── App.jsx           # Main UI state and auth gate
        ├── api/auth.js       # Login, session, analyze API calls
        └── components/       # FileUpload, LoginPage, ResultDisplay, etc.
```

| File | Role |
|------|------|
| `parser.py` | Converts raw log text into typed records using a fixed HTTP access log format |
| `embedder.py` | Batch-embeds parsed records via Azure OpenAI |
| `indexer.py` | Pushes records + vectors into the Azure AI Search index |
| `search.py` | Finds historically similar log lines using vector search |
| `main.py` | Builds the GPT prompt, injects similar-pattern context, returns analysis |
| `api.py` | HTTP API layer connecting the pipeline to the React dashboard |
| `security.py` | Dashboard login, JWT validation, rate limiting, file size limits |
| `blob_reader.py` | Alternative ingestion path from Azure Blob Storage |

---

## Supported Log Format

Each line must match this HTTP access log pattern:

```
2026-06-12 03:13:01 WARN 45.33.32.156 GET /api/internal/admin 403 12ms
```

Fields: `timestamp`, `level`, `ip`, `method`, `endpoint`, `status`, `latency_ms`.

See `sample_logs/test.log` for a working example.

---

## Setup

### Prerequisites

- Python 3.11+
- Node.js 18+
- Azure resources: OpenAI (chat + embedding deployments), AI Search index, Blob Storage container

### 1. Clone and configure environment

```bash
git clone <repo-url>
cd Logsentinel
python -m venv venv

# Windows
.\venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env   # then fill in your values
```

### 2. Environment variables

Copy `.env.example` → `.env` and set:

**Application & security**
```
APP_ENV
DASHBOARD_USERNAME
DASHBOARD_PASSWORD
API_KEY                  # required in production
JWT_SECRET               # optional; falls back to API_KEY
JWT_EXPIRE_HOURS
CORS_ORIGINS
AUTH_DISABLED            # dev-only bypass; ignored in production
```

**Upload limits**
```
MAX_UPLOAD_BYTES
MAX_LOG_LINES
RATE_LIMIT_REQUESTS
RATE_LIMIT_WINDOW_SECONDS
```

**Azure OpenAI**
```
AZURE_OPENAI_ENDPOINT
AZURE_OPENAI_KEY
AZURE_OPENAI_DEPLOYMENT
AZURE_OPENAI_EMBEDDING_DEPLOYMENT
```

**Azure Blob Storage** (for CLI / script ingestion)
```
AZURE_STORAGE_CONNECTION_STRING
AZURE_STORAGE_CONTAINER
```

**Azure AI Search**
```
AZURE_SEARCH_ENDPOINT
AZURE_SEARCH_KEY
AZURE_SEARCH_INDEX
```

### 3. Run the backend

```bash
uvicorn api:app --reload
```

API available at `http://localhost:8000`  
Swagger UI (dev only): `http://localhost:8000/docs`

### 4. Run the dashboard

```bash
cd dashboard
npm install
cp .env.example .env    # set VITE_API_URL if needed
npm run dev
```

Dashboard available at `http://localhost:3000`

Sign in with `DASHBOARD_USERNAME` / `DASHBOARD_PASSWORD`, upload `sample_logs/test.log`, and click **Analyze logs**.

---

## Example Output

Given `sample_logs/test.log`, GPT returns compact markdown findings like:

```markdown
**[Severity: High] Repeated admin endpoint probing from external IP**
- IP/Source: 45.33.32.156
- Pattern: Five GET requests to /api/internal/admin in 4 seconds, all returned 403.
- Risk: External IP rapidly probing a restricted admin endpoint - consistent with automated scanning or brute-force reconnaissance.
- Action: Block or rate-limit 45.33.32.156 at the firewall/WAF and review access controls on /api/internal/*.

**[Severity: Medium] Rapid internal access to user endpoint**
- IP/Source: 10.0.0.5
- Pattern: Three consecutive GET /api/internal/users requests within 2 seconds, all 200 OK.
- Risk: High-frequency access to an internal data endpoint may indicate scraping or automated data collection.
- Action: Verify whether 10.0.0.5 is authorized for bulk access; audit returned data volume.
```

The API response also includes:

```json
{
  "analysis": "**[Severity: High] Repeated admin endpoint probing...",
  "records_processed": 12,
  "similar_patterns_found": 5
}
```

---

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/health` | Health check |
| `GET` | `/auth/config` | Whether login is required |
| `POST` | `/auth/login` | Dashboard login → JWT |
| `GET` | `/auth/session` | Validate current session |
| `POST` | `/analyze` | Upload log file → analysis (requires JWT or `X-API-Key`) |

---

## Security

LogSentinel includes baseline protections suitable for an MVP deployment:

- **Dashboard login** - username/password with JWT sessions (required by default)
- **API key** - `X-API-Key` header for server-to-server automation
- **Rate limiting** - per-IP request throttling (in-memory)
- **Upload validation** - file type, size, and line-count limits
- **CORS** - configurable allowed origins
- **Security headers** - `X-Frame-Options`, `HSTS` (production), etc.
- **Swagger disabled** in production

---

## Current Limitations

This is an MVP. Known constraints:

- **Single log format** - only the regex-defined HTTP access log schema is supported; no JSON, syslog, or CloudTrail parsing.
- **Batch only** - files are uploaded and processed end-to-end; no live log streaming.
- **Index ID collisions** - record IDs are positional (`0`, `1`, `2`…); re-uploading overwrites prior entries in the same index batch.
- **In-memory rate limiting** - does not scale across multiple API instances without Redis or similar.
- **Azure cost & latency** - each analysis triggers embedding + search + GPT calls; large files can take 30-90 seconds.
- **GPT variability** - output format is prompt-guided but not schema-validated; occasional verbosity or missed findings are possible.
- **Similarity search scope** - vector search runs on suspicious records (`WARN`, HTTP ≥ 400) only; benign traffic is not used as search queries.
- **No multi-tenancy** - single shared index and credentials; no per-org isolation.
- **Learning project** - not hardened to enterprise SOC requirements (no SSO, no audit log, no alert routing).

---

## Future Improvements

- Support additional log formats (JSON, Apache, nginx combined)
- Persistent analysis history and case management UI
- Redis-backed rate limiting and job queue for async processing
- UUID-based document IDs and index versioning
- SSO / Azure AD integration for dashboard auth
- Structured output schema (JSON findings) alongside markdown
- Deploy backend to Azure App Service and frontend to Static Web Apps
- Alert integrations (email, Teams, webhook)

---

_Full reasoning behind these limits - and the fixes I'd apply - is in [DESIGN_NOTES.md](DESIGN_NOTES.md)._