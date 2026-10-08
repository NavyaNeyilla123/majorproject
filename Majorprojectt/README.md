# KnowledgeOps AI

AI-powered project intelligence workspace that turns fragmented enterprise
knowledge (GitHub, Gmail, cross-source relationships) into ranked evidence,
cited claims, and actionable release decisions.

**Stack:** React + Vite frontend · FastAPI backend · synthetic GitHub/Gmail
dataset (JSON, read in place — never copied or modified) · Qdrant vector
store · local deterministic embeddings.

---

## Quick start

```bash
# Backend (port 8000)
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000

# Frontend (port 5173, proxies /api to :8000)
npm install
npm run dev
```

Tests and build:

```bash
python -m pytest backend/tests -q   # 163 passed, 2 skipped (opt-in live tests)
npm run build                        # production build
```

---

## Step 8: RAG + Qdrant

Retrieval-augmented generation layer over the synthetic dataset. The pipeline:

```
MockMCPProvider → RAGDocument → chunking → embeddings (local-hash, 1536d)
  → Qdrant (knowledgeops_projects)
  → hybrid retrieval (vector + keyword + metadata)
  → deterministic rerank → RetrievalAgent → AnalysisAgent
```

### Vector store modes

| Mode | Configuration | Behavior |
|---|---|---|
| **embedded** (default) | `QDRANT_URL` empty | qdrant-client embedded, persistent at `QDRANT_PATH` (`backend/.rag_storage`) |
| **server** | `QDRANT_URL=http://localhost:6333` | real Qdrant server, optional `QDRANT_API_KEY` |
| **memory** | tests | in-process `InMemoryVectorStore`, no persistence |

An unreachable store is always reported honestly as `unavailable` with a
clear message — never as connected.

### Environment variables

See `backend/.env.example`:

| Variable | Default | Purpose |
|---|---|---|
| `QDRANT_URL` | `` (empty) | empty = embedded mode; set = server mode |
| `QDRANT_API_KEY` | `` | API key for server mode (never committed) |
| `QDRANT_COLLECTION` | `knowledgeops_projects` | collection name |
| `QDRANT_PATH` | `backend/.rag_storage` | embedded storage path |
| `EMBEDDING_PROVIDER` | `local-hash` | deterministic local embeddings (no paid API) |
| `EMBEDDING_DIM` | `1536` | embedding dimensions |
| `RAG_TOP_K` | `10` | default number of chunks per search |
| `MCP_PROVIDER` | `mock` | source provider (`mock` default; `real` = Step 10 adapter, opt-in) |

### RAG endpoints

| Endpoint | Method | Purpose |
|---|---|---|
| `/api/rag/status` | GET | honest index health: `status`, `collection`, `documents`, `chunks`, `last_indexed`, `embedding`, `mode` |
| `/api/rag/index` | POST | idempotent (re)index of all source documents |
| `/api/rag/search` | POST | hybrid search: `{query, project_id?, top_k?}` → ranked chunks with score breakdowns |
| `/api/ingest` | POST | legacy alias for `/api/rag/index` |

Unavailable vector store → `503` with a clear detail message; status stays
`200` with `status: "unavailable"`.

### How ranking works

Each chunk receives an explainable score:

```
hybrid  = 0.50·vector + 0.35·keyword + 0.15·metadata
rerank  = 0.70·hybrid + 0.15·title_overlap + 0.10·query_coverage
          + 0.05·project + 0.12·linked (cross-record expansion)
```

- **vector** — cosine similarity of local-hash embeddings (stopwords removed)
- **keyword** — overlap of query/content tokens
- **metadata** — source type + timestamp recency
- **linked** — chunks linked to a top candidate (issue ↔ PR, cross-source
  link) are expanded with a decaying score; same-conversation records
  (thread ↔ emails) are excluded to avoid flooding

Every result exposes `score_breakdown` (vector/keyword/metadata/hybrid) and
`rerank_reasons`, so any ranking can be explained without an LLM.

### RetrievalAgent integration

The MCP selection runs first, unchanged. RAG chunks are then merged in,
deduplicated by parent `source_id`: existing records are never modified,
RAG-only records are appended with `relationships: {rag_chunk, rag_score}`
(capped at 5) and filtered by `project_id`. An empty index or an
unreachable store degrades to MCP-only results with an explicit stage
detail — a query never fails because of RAG.

### Frontend

The **Retrieval and index health** card on *MCP Connections* is bound to
`GET /api/rag/status`: live badge (Connected / Unavailable), collection,
indexed documents/chunks, last indexed timestamp, embedding provider, and
mode. Helpers live in `src/services/api.js`
(`fetchRagStatus`, `indexRag`, `searchRag`).

### Testing

`backend/tests/conftest.py` isolates every run: `QDRANT_URL=""`, a temp
`QDRANT_PATH`, and an in-memory store — tests never touch the persistent
embedded index. `backend/tests/test_rag.py` covers document loading,
chunking, embeddings, indexing idempotency, explainable hybrid scores,
project filters, rerank determinism, provenance, the critical retrieval
scenario (all three blocker records in the top-10 for each of the three
question phrasings), all RAG endpoints, and RetrievalAgent merge/degradation
behavior.

---

## Step 9: LLM Integration

A sixth pipeline stage generates the final answer from grounded context:

```
Planner → Retrieval (MCP + RAG) → Analysis → LLM Agent → Workflow → Evidence
```

The LLM never performs retrieval: `build_llm_context()` projects only what
the earlier stages produced (question, retrieved records, analysis output,
cross-source links) into an `LLMContext`, and `build_prompt()` labels those
sections (`[QUESTION]`, `[PROJECT]`, `[GITHUB EVIDENCE]`, `[GMAIL EVIDENCE]`,
`[RAG RESULTS]`, `[ANALYSIS]`, `[CROSS-SOURCE RELATIONSHIPS]`) around a fixed
system prompt that forbids invented facts, source IDs, people, dates,
approvals and completed actions.

### Provider configuration

See `backend/.env.example`:

| Variable | Default | Purpose |
|---|---|---|
| `LLM_PROVIDER` | `mock` | `mock` (deterministic, no network) or `openai-compatible` (`openai`, `http` aliases); empty/unknown → unavailable |
| `LLM_MODEL` | `gpt-4o-mini` (HTTP only) | model name for HTTP providers |
| `LLM_API_KEY` | `` | required for HTTP providers; never committed, never returned by any endpoint |
| `LLM_BASE_URL` | `https://api.openai.com/v1` | OpenAI-compatible base URL |
| `LLM_TIMEOUT_SECONDS` | `30` | HTTP request timeout |

Providers resolve lazily at call time (mirroring the MCP seam), so tests can
switch them through the environment. The mock provider is the default and the
only provider exercised in this environment; the HTTP provider is
OpenAI-compatible via `httpx` with no SDK dependency.

### Grounded flow, validation, confidence

- **Mock provider** composes the answer strictly from `LLMContext`: status
  sentence, analysis blockers/facts/decisions/unresolved actions, and echoed
  analysis claims. Actor questions ("who…") without explicit actor evidence in
  the records get an honest "the available evidence does not identify…"
  answer instead of a name.
- **Response parsing** accepts bare/fenced/embedded JSON, requires a
  non-empty `answer`, normalizes lists and clamps confidence to `[0, 1]`;
  anything else raises `LLMParseError` (never reaches the client).
- **Evidence validation** rejects claims whose cited `source_id` was not
  retrieved, whose `source_type` mismatches, or whose text does not overlap
  the cited record — fabricated IDs (e.g. `Issue #999`) never enter the
  pipeline evidence.
- **Sentence-level guards** strip unsupported delay claims (`will be delayed`,
  `confirmed delay`, …) and unsupported execution claims (`was assigned`,
  `was approved`, `was merged`, …) unless the retrieved records confirm them,
  then scrub remaining forbidden phrases case-insensitively. An answer too
  short after stripping falls back to the deterministic composer.
- **Confidence** = `min(evidence_tier, llm_tier)`, downgraded when any claim
  or list item was rejected, `low` when evidence is weak, and capped
  `high → medium` whenever the Analysis Agent recorded contradictions —
  an LLM number alone can never raise it.
- **Workflow stays authoritative for actions**: `recommended_actions` is
  still generated only by the Workflow Agent; LLM-suggested actions are
  validated and stored on `llm_response` as informational output.

### Deterministic fallback

Any provider, parsing or validation error is caught inside `LLM Agent`:
the stage completes with detail
`llm unavailable (<Type>: <reason>) · deterministic fallback`,
`llm_used` is `false`, and the answer comes from the existing
`compose_final_answer()` — a run never fails because of the LLM stage.

### Endpoint

`GET /api/llm/status` → `{provider, model, configured, status, message}` with
`status` one of `healthy` (mock), `configured` (HTTP key present, live
connectivity explicitly *not* tested) or `unavailable`. Credentials are
structurally absent from the response; HTTP errors are sanitized
(`sk-…`/`Bearer …` redacted) before they appear in stage details.

### Frontend

The **LLM settings** card on *Settings* is bound to `GET /api/llm/status`
(via `fetchLlmStatus` in `src/services/api.js`): real provider/model, status
badge (Healthy/Configured/Unavailable), honest credential row, and the status
message. No other UI changed; answer views already render answer, evidence,
confidence and the stage trace (now including `LLM Agent`).

### Testing

`backend/tests/test_llm.py` (34 tests) covers provider abstraction, mock
grounding, prompt construction, structured parsing, malformed output,
evidence validation, fabrication rejection, confidence tiers, unavailable
fallback, status honesty (including credential hiding), the query endpoint,
the full pipeline snapshot, RAG + LLM together, at-risk≠delayed and
action≠executed regressions, and the hallucination scenario ("Who approved…"
→ "does not identify", no participant names, supported claims only).

---

## Step 10: Real GitHub + Gmail MCP (opt-in)

The same `MCPProvider` seam now has a second implementation. `MCP_PROVIDER=mock`
stays the default and is untouched; setting `MCP_PROVIDER=real` switches to a
read-only adapter that talks to actual GitHub/Gmail MCP servers. There is no
fallback: real-mode failures raise a clear `MCPProviderError` and are reported
honestly — the adapter never claims a server is connected without a successful
live `tools/list`.

### Architecture

```
RealMCPProvider
  └─ MCPConnection (per server: github, gmail)
       ├─ config from env: MCP_<SERVER>_URL (streamable HTTP)
       │                  or MCP_<SERVER>_COMMAND/ARGS (stdio)
       ├─ one session per operation (asyncio.run + connect/call timeouts)
       ├─ live tools/list → DiscoveredTool list (cached per config)
       └─ capability_map: operation key → advertised tool (heuristics + MCP_<SERVER>_MAP)
            └─ write/action verbs excluded from binding, always
```

- **Capability binding** never assumes tool names: operations
  (`search.issues`, `get.pull_request`, `search.threads`, …) are matched
  against the server's live tool list by token heuristics, overridable with
  `MCP_GITHUB_MAP` / `MCP_GMAIL_MAP` JSON. An operation that matches nothing
  fails with an unsupported-capability error naming the discovered tools.
- **Read-only guarantee**: any tool whose name contains a write verb
  (`create`, `update`, `send`, `delete`, …) is excluded from binding —
  including through explicit maps.
- **Argument building** is schema-driven: parameters the adapter cannot supply
  (e.g. `owner`/`repo` without `MCP_GITHUB_OWNER`/`MCP_GITHUB_REPO`, or
  `userId` without `MCP_GMAIL_USER_ID`) produce a clear configuration error
  rather than a malformed call.
- **Payload normalization** maps GitHub issues/PRs/commits/reviews/repos and
  Gmail threads/messages into the existing `MCPRecord` shape with
  `source_mode="real"`; real IDs and URLs are preserved verbatim, and
  not-found results return `None`.
- **Secrets** are never stored, logged, or returned: tokens are read from
  env (`MCP_GITHUB_TOKEN` or `MCP_GITHUB_TOKEN_ENV`), and every error message
  is redacted before it leaves the transport.

### Configuration

See `backend/.env.example` (Step 10 block). Summary:

| Variable | Default | Purpose |
|---|---|---|
| `MCP_PROVIDER` | `mock` | `mock` (offline default) or `real` |
| `MCP_GITHUB_URL` / `MCP_GITHUB_COMMAND` | unset | GitHub MCP server transport |
| `MCP_GITHUB_TOKEN` / `MCP_GITHUB_TOKEN_ENV` | unset | PAT value, or env var name holding it |
| `MCP_GITHUB_OWNER` / `MCP_GITHUB_REPO` | unset | default repository scope |
| `MCP_GITHUB_MAP` | unset | JSON operation→tool override |
| `MCP_GMAIL_COMMAND` / `MCP_GMAIL_URL` | unset | Gmail MCP server transport (community stdio server) |
| `MCP_GMAIL_USER_ID` | `me` | Gmail API userId |
| `MCP_GMAIL_MAP` | unset | JSON operation→tool override |
| `MCP_CONNECT_TIMEOUT_MS` / `MCP_CALL_TIMEOUT_MS` | `10000` / `15000` | per-operation timeouts |
| `RAG_REAL_COLLECTION` | `knowledgeops_real` | separate vector collection for real documents |

**Not configured in this environment:** no GitHub PAT, no Gmail OAuth
credentials, and no MCP server installed. Gmail is wired to the community
stdio server (`@gongrzhe/server-gmail-autoauth-mcp`) but stays `unconfigured`
until OAuth credentials exist. `GET /api/mcp/status` reports `unconfigured`
for both servers here — that is the honest state.

### RAG isolation

Real documents never touch the synthetic collection: indexing under
`MCP_PROVIDER=real` targets `knowledgeops_real` (`RAG_REAL_COLLECTION`),
document IDs are prefixed `real:`, and every chunk carries
`source_mode: "real"`. `knowledgeops_projects` and the JSON dataset are
read-only and unchanged; synthetic IDs (`142`, `284`, `GM-064`) never appear
in real-mode logic.

### Status endpoint

`GET /api/mcp/status` returns 200 in real mode with `mode`, `github`/`gmail`
objects (`status`: `connected` only after a live `tools/list`, else
`unconfigured`/`unavailable`/`error`), and the actual discovered tool names.
No response ever claims connectivity that was not verified.

### Frontend

*MCP Connections* and *Settings* render the real statuses: Connected /
Unconfigured / Unavailable / Error badges per server, the discovered tool
count, and the honest detail message (e.g. "No real MCP connectivity" in
mock mode). No layout changes.

### Testing

`backend/tests/test_mcp_real.py` (~54 tests) runs entirely against injected
fake MCP sessions — no network, no processes, no credentials: provider
selection without fallback, discovery states, capability binding and map
overrides, write-tool exclusion, GitHub/Gmail normalization, scoping
errors, health/status honesty, secret redaction, RAG collection isolation,
retrieval/evidence with the real provider, and a source scan asserting no
hardcoded synthetic IDs. Two live tests run only with
`MCP_INTEGRATION_TESTS=1`.

---

## Project layout

```
backend/
  app/
    api/        # FastAPI routers (health, query, mcp, rag, llm, ...)
    agents/     # Planner → Retrieval → Analysis → LLM → Workflow → Evidence
    llm/        # Step 9: provider seam, prompt builder, parser, validator
    mcp/        # mock + real (Step 10) provider seam, transport, capability map
    rag/        # Step 8: loader, chunker, embeddings, qdrant, hybrid retrieval
    core/       # settings
  tests/        # pytest suite (163 tests)
data/           # synthetic GitHub/Gmail dataset (read-only, never copied)
src/            # React frontend
```

## Current status

- Steps 1–10 implemented. MCP provider: `mock` default (synthetic data,
  honest status) with an opt-in `real` adapter (Step 10) that is read-only,
  never falls back, and reports `unconfigured` until a GitHub/Gmail MCP
  server is actually configured. LLM provider: `mock` (deterministic,
  grounded, default) with an OpenAI-compatible HTTP option that requires
  `LLM_API_KEY`.
- Real integrations are not configured in this environment: no GitHub PAT,
  no Gmail OAuth credentials, no MCP server installed — status endpoints
  report this honestly (`unconfigured`), never a false `connected`.
