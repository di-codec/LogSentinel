# Design Notes

This document covers the *why* behind LogSentinel - the design decisions, the
tradeoffs I accepted, the known limitations, and what I'd change with more time.
The [README](README.md) explains what the project does and how to run it; this is
the engineering-judgment layer underneath it.

---

## Design decisions

Each decision is written as **what I chose → why → what it costs**.

### RAG over logs, not rule matching
Rule-based alerting answers *"did this line match a signature?"* LogSentinel
answers *"is this pattern unusual compared to what I've seen, and what does it
mean?"* Parsed records are embedded, similar historical records are retrieved by
vector similarity, and that context is handed to the model so findings come with
an explanation and a recommended action rather than a raw alert.
**Tradeoff:** it augments an analyst, it does not replace a production SIEM - and
it inherits LLM cost, latency, and non-determinism, which is why the next decision
exists.

### Vector search runs only on suspicious records
Similarity search and model context are built from lines that already look
interesting (`WARN`/`ERROR` level or HTTP status ≥ 400), not from every line in
the file.
**Why:** running retrieval over all traffic multiplies embedding calls and search
queries linearly with log size, for almost no signal on the 200-OK majority.
**Tradeoff:** a genuinely novel attack that produces only clean 2xx responses
would be under-weighted. Acceptable for the current threat model (probing,
enumeration, error-generating abuse); revisited if the input mix changes.

### Two authentication paths: JWT for humans, API key for machines
The dashboard logs in with username/password and receives a short-lived JWT
(`Bearer`); server-to-server callers use a static `X-API-Key`. A single
`require_auth` dependency accepts either.
**Why:** the two callers have different lifecycles - a browser session should
expire, a backend integration should not need to re-login.
**Tradeoff:** two code paths to keep in sync; mitigated by routing both through
one dependency.

### Constant-time credential comparison + a dedicated login limiter
Credentials are compared with `secrets.compare_digest` (constant-time, no timing
side channel), and login attempts are rate-limited *separately* from the global
request limiter (5 attempts / 5 min per IP).
**Why:** a naive `==` leaks timing information, and a global limiter tuned for
normal traffic is too loose to slow credential stuffing.
**Tradeoff:** the login limiter keeps per-IP state in memory - see limitations.

### Fail-fast startup validation
On boot the app refuses to start if it is not explicitly in a safe state:
dashboard credentials must be set unless `AUTH_DISABLED=true` is deliberately
chosen for local dev, and `API_KEY` is mandatory when `APP_ENV=production`.
Missing Azure env vars also abort startup.
**Why:** a security tool silently booting wide-open is worse than not booting.
**Tradeoff:** slightly less convenient first-run; intentional.

### Hardened by default
In production, interactive docs (`/docs`, `/redoc`, `/openapi.json`) are disabled,
error responses are generic (detailed messages only in dev), and every response
carries `nosniff`, `X-Frame-Options: DENY`, a strict referrer policy, and HSTS.
**Why:** reduce attack surface and avoid leaking internals through error text or a
live schema.
**Tradeoff:** debugging a prod issue is harder without the detailed errors - a
deliberate exchange.

### Batch embedding in a single call
All records in a file are embedded in one Azure OpenAI request rather than one
call per line.
**Why:** fewer round-trips, lower latency, fewer rate-limit hits.
**Tradeoff:** a single very large file can exceed the model's per-request batch
limit; bounded today by the upload size and line-count caps.

---

## Known limitations & what I'd change next

These are the honest edges. Each one has a concrete fix I'd reach for.

- **Document IDs are positional.** Records are indexed with `id = str(i)` where
  `i` is the position in the batch. Uploading a second file reuses `"0"`, `"1"`,
  `"2"`… and overwrites the previous batch in the index.
  *Fix:* derive the ID from a UUID or a content hash of the record.

- **Rate limiting and login tracking are in-memory.** Counters live in a
  per-process dict, so they reset on restart and don't coordinate across multiple
  workers or instances - the limit effectively multiplies by the number of
  processes.
  *Fix:* move the counters to a shared store (Redis) keyed the same way.

- **`X-Forwarded-For` is trusted as-is.** The client IP used for rate limiting is
  taken from the first value of that header. Behind a trusted proxy that overwrites
  it, that's correct; exposed directly, a caller can spoof it and sidestep the
  limiter.
  *Fix:* only trust the header from a known proxy hop, or use the right-most
  untrusted address.

- **One hardcoded log format.** Parsing is a single regex for one timestamped
  access-log shape; lines that don't match are silently dropped with no feedback
  on how many were skipped.
  *Fix:* a small registry of pluggable parsers and a reported count of unparsed
  lines so the analyst knows coverage.

- **The JWT secret has a dev fallback.** If neither `JWT_SECRET` nor `API_KEY` is
  set, signing falls back to a hardcoded development secret. It's safe in
  production *only* because startup validation forces `API_KEY` there - but that
  safety is implicit.
  *Fix:* remove the fallback and fail closed if no signing secret is configured.

- **No automated tests yet.** The parser and the auth logic are the highest-value,
  most testable units.
  *Next:* `pytest` around `parse_log_file` (format edge cases, malformed lines)
  and the token/credential paths, plus a minimal CI check on push.

---

## Deployment lessons (Azure App Service)

Real gotchas from getting this onto Azure, kept here because they cost the most
time and aren't in any tutorial:

- **Free F1 tier is for static exploration, not iterative deploys.** Cold starts
  are slow and start attempts burn the CPU quota (`QuotaExceeded`, 230s container
  timeouts). Basic B1 is the practical floor for actively deploying a Python app.

- **"Deployment succeeded" does not mean the app is running.** A green Deployment
  Center only means files copied and `pip install` ran. Verify the process
  separately: `az webapp show --query state`.

- **The zip must have files at the root.** `api.py` directly at the archive root,
  not nested inside a project folder - otherwise the startup command can't find
  the app.

- **Env var names must match the Azure OpenAI deployment names exactly.** A spelling
  mismatch between App Settings and the actual deployment surfaces as
  `DeploymentNotFound` at request time, not at startup.