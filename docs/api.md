# Enterprise Knowledge Agent: OpenAPI & REST API Reference

> Production REST API specification for the **Enterprise Knowledge Agent**.

---

## 1. Global Ingress, Authentication & Headers

### Base URL
All API routes are served under prefix:
```
http://localhost:8000/api/v1
```

### Security Scheme (Bearer JWT)
All secured endpoints require an HTTP Bearer JWT token in the `Authorization` header:
```http
Authorization: Bearer <jwt-token>
```

### Context & Tracing Headers
| Header | Type | Description | Default |
|---|---|---|---|
| `Authorization` | `string` | Signed JWT Bearer token | Required on secured endpoints |
| `X-Correlation-ID` | `string` | Distributed tracing UUID propagated across logs & MCP | Auto-generated if omitted |
| `X-Tenant-ID` | `string` | Multi-tenant tenant identifier | `tenant-nimbus-default` |

### Rate Limiting Headers (Returned on all responses)
| Header | Description |
|---|---|
| `X-RateLimit-Limit-User` | Max requests permitted per minute per user (30) |
| `X-RateLimit-Remaining-User` | Remaining query budget for calling user |
| `X-RateLimit-Limit-Tenant` | Max requests permitted per minute per tenant (100) |
| `X-RateLimit-Remaining-Tenant` | Remaining query budget for tenant organization |

---

## 2. Authentication Endpoints (`/auth`)

### 2.1 Authenticate with Credentials
`POST /api/v1/auth/login`

Authenticates corporate email and password against salted PBKDF2 hash and issues a signed permission-bearing JWT access token.

#### Request Body
```json
{
  "email": "bob@nimbus.com",
  "password": "correct_password"
}
```

#### Response (`200 OK`)
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "expires_in_minutes": 60,
  "user": {
    "user_id": "mgr_bob",
    "email": "bob@nimbus.com",
    "full_name": "Bob Martinez",
    "roles": ["manager"],
    "groups": ["group_engineering", "group_managers"],
    "clearance": "CONFIDENTIAL",
    "tenant_id": "tenant-nimbus-default"
  }
}
```

---

### 2.2 Mint Persona Token (Demo & Testing)
`POST /api/v1/auth/token`

Mints a cryptographically signed JWT token for a pre-configured corporate persona.

#### Request Body
```json
{
  "user_id": "emp_alice",
  "email": "alice@nimbus.com",
  "full_name": "Alice Chen",
  "roles": ["employee"],
  "groups": ["group_engineering", "all-staff"],
  "clearance": "INTERNAL",
  "tenant_id": "tenant-nimbus-default"
}
```

#### Response (`200 OK`)
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "expires_in_minutes": 60,
  "user": {
    "user_id": "emp_alice",
    "email": "alice@nimbus.com",
    "full_name": "Alice Chen",
    "roles": ["employee"],
    "groups": ["group_engineering", "all-staff"],
    "clearance": "INTERNAL",
    "tenant_id": "tenant-nimbus-default"
  }
}
```

---

### 2.3 Inspect Authenticated Profile
`GET /api/v1/auth/me`

Returns the current authenticated user's principal, clearance, and group memberships.

#### Response (`200 OK`)
```json
{
  "user_id": "emp_alice",
  "email": "alice@nimbus.com",
  "full_name": "Alice Chen",
  "roles": ["employee"],
  "groups": ["group_engineering", "all-staff"],
  "clearance": "INTERNAL",
  "tenant_id": "tenant-nimbus-default"
}
```

---

## 3. Chat & Agent Completion Endpoints (`/chat`)

### 3.1 Execute Agent Chat Completion
`POST /api/v1/chat/completions`

Dispatches a stateful agent reasoning workflow across the authorized enterprise knowledge base with Self-RAG reflection, claim verification, conflict resolution, and MCP tool execution.

#### Request Body
```json
{
  "query": "What is our company's approved daily travel meal per diem rate?",
  "thread_id": "3c8e4f1a-b62e-4b2a-89a1-5f33bc123456",
  "stream": false,
  "approval_granted": null
}
```

#### Response: Standard Factual Answer (`200 OK`)
```json
{
  "query": "What is our company's approved daily travel meal per diem rate?",
  "answer": "Employees traveling on authorized company business are entitled to $125.00 per day domestic meal per diem ($160.00 in Tier-1 cities). Reasonable client entertainment dining including wine/beer is reimbursable when accompanied by client name and business purpose. [Nimbus Corporate Travel and Business Expense Policy 2026, Daily Meal Per Diem]",
  "citations": [
    {
      "doc_id": "fin-travel-policy-2026",
      "title": "Nimbus Corporate Travel and Business Expense Policy 2026",
      "section_path": "Daily Meal Per Diem",
      "source": "local_folder",
      "source_url": ""
    }
  ],
  "confidence": 0.95,
  "conflict_notices": [
    "Document 'Nimbus Corporate Travel and Business Expense Policy 2026' (approved, 2026) supersedes older/deprecated document 'Nimbus Corporate Travel and Business Expense Policy 2024' regarding 'travel and business expense policy'."
  ],
  "steps_executed": [
    "understand",
    "rewrite_and_plan",
    "retrieve",
    "grade_evidence",
    "resolve_conflicts",
    "generate",
    "verify",
    "decide_action",
    "respond"
  ],
  "approval_required": false,
  "thread_id": "3c8e4f1a-b62e-4b2a-89a1-5f33bc123456"
}
```

#### Response: High-Risk Action Requiring Human Approval (`200 OK`)
When an action request maps to a `write_high` MCP tool (e.g. `create_jira_ticket`), execution halts:
```json
{
  "query": "Create a Jira ticket to patch OpenSSL vulnerability in staging",
  "answer": "Action create_jira_ticket requires human approval before proceeding.",
  "citations": [],
  "confidence": 0.9,
  "conflict_notices": [],
  "steps_executed": [
    "understand",
    "rewrite_and_plan",
    "retrieve",
    "grade_evidence",
    "resolve_conflicts",
    "generate",
    "verify",
    "decide_action",
    "human_approval",
    "respond"
  ],
  "approval_required": true,
  "thread_id": "3c8e4f1a-b62e-4b2a-89a1-5f33bc123456"
}
```

#### Resuming with Human Approval Decision
Client re-submits the request with the same `thread_id` and `approval_granted: true`:
```json
{
  "query": "Create a Jira ticket to patch OpenSSL vulnerability in staging",
  "thread_id": "3c8e4f1a-b62e-4b2a-89a1-5f33bc123456",
  "approval_granted": true
}
```
**Response upon Approval**:
```json
{
  "query": "Create a Jira ticket to patch OpenSSL vulnerability in staging",
  "answer": "Action create_jira_ticket completed: Ticket NIMBUS-1052 has been successfully created: https://jira.corp.internal/browse/NIMBUS-1052 (Priority: High, Status: Open).",
  "citations": [],
  "confidence": 1.0,
  "conflict_notices": [],
  "steps_executed": [
    "understand",
    "rewrite_and_plan",
    "retrieve",
    "grade_evidence",
    "resolve_conflicts",
    "generate",
    "verify",
    "decide_action",
    "human_approval",
    "respond"
  ],
  "approval_required": false,
  "thread_id": "3c8e4f1a-b62e-4b2a-89a1-5f33bc123456"
}
```

---

### 3.2 SSE Streaming Chat Completion
`POST /api/v1/chat/completions` with `"stream": true`

Streams real-time agent thought steps, reflection loops, draft generation, and citations via Server-Sent Events (SSE).

#### Response Stream (`text/event-stream`)
```
data: {"event": "step", "node": "understand", "steps": ["understand"]}

data: {"event": "step", "node": "rewrite_and_plan", "steps": ["rewrite_and_plan"]}

data: {"event": "step", "node": "retrieve", "steps": ["retrieve"]}

data: {"event": "step", "node": "grade_evidence", "steps": ["grade_evidence"]}

data: {"event": "step", "node": "generate", "draft_answer": "Employees traveling on authorized...", "steps": ["generate"]}

data: {"event": "step", "node": "respond", "final_response": "...", "citations": [...], "steps": ["respond"]}

data: [DONE]
```

---

## 4. Admin & Evaluation Endpoints (`/admin`)

### 4.1 Retrieve RAGAS Benchmark Results
`GET /api/v1/admin/eval/results`

Returns the latest comparative empirical benchmark results comparing Enterprise Agentic RAG against the Naive Baseline over the 15-case Golden Dataset.

#### Response (`200 OK`)
```json
{
  "timestamp": "2026-11-08T03:23:40.000000Z",
  "hypothesis_proven": true,
  "agent_summary": {
    "system_name": "Enterprise Agentic RAG",
    "total_queries": 15,
    "mean_faithfulness": 0.98,
    "mean_answer_relevance": 0.92,
    "mean_context_precision": 0.91,
    "mean_context_recall": 0.89,
    "permission_leak_rate_percent": 0.0,
    "conflict_resolution_accuracy_percent": 93.33,
    "abstention_accuracy_percent": 80.0,
    "p50_latency_ms": 28.5,
    "p95_latency_ms": 54.2
  },
  "baseline_summary": {
    "system_name": "Naive RAG Baseline",
    "total_queries": 15,
    "mean_faithfulness": 0.72,
    "mean_answer_relevance": 0.65,
    "mean_context_precision": 0.58,
    "mean_context_recall": 0.64,
    "permission_leak_rate_percent": 66.67,
    "conflict_resolution_accuracy_percent": 20.0,
    "abstention_accuracy_percent": 0.0,
    "p50_latency_ms": 12.0,
    "p95_latency_ms": 22.0
  }
}
```

---

## 5. System Health & Observability Endpoints

### 5.1 Liveness Probe
`GET /api/v1/health`

Verifies that the FastAPI process is responsive.
```json
{
  "status": "healthy",
  "app": "Enterprise Knowledge Agent",
  "environment": "development",
  "timestamp": "2026-11-09T01:50:00.000000Z",
  "version": "0.1.0"
}
```

### 5.2 Readiness Probe
`GET /api/v1/health/ready`

Verifies operational connectivity to PostgreSQL, Qdrant, and Redis/cache.
```json
{
  "ready": true,
  "components": {
    "database": { "status": "healthy", "details": "Operational" },
    "vector_store": { "status": "healthy", "details": "Qdrant pre-filter ready" },
    "cache": { "status": "healthy", "details": "Redis/in-memory cache ready" }
  },
  "timestamp": "2026-11-09T01:50:00.000000Z"
}
```

### 5.3 Prometheus Metrics Exposition
`GET /api/v1/metrics`

Returns standard Prometheus metrics for QPS, latency histograms, token burn, and permission leak alerts.

---

## 6. HTTP Error Response Format

All error responses conform to standard RFC 7807 problem details:

```json
{
  "error": {
    "code": "PERMISSION_LEAK_PREVENTED",
    "message": "User 'emp_alice' is not authorized to access documents with classification 'CONFIDENTIAL'.",
    "status": 403,
    "correlation_id": "a90df23e-812d-4f12-a7d1-0987bc543210"
  }
}
```

| HTTP Status | Error Code | Description |
|---|---|---|
| `401 Unauthorized` | `UNAUTHORIZED` | Missing, expired, or invalid Bearer JWT token |
| `403 Forbidden` | `FORBIDDEN` | Insufficient user clearance or group membership |
| `404 Not Found` | `NOT_FOUND` | Document, ticket, or user entity does not exist |
| `422 Unprocessable` | `VALIDATION_ERROR` | Request payload fails Pydantic schema validation |
| `429 Too Many Requests` | `RATE_LIMIT_EXCEEDED` | Exceeded per-minute user or tenant query quota |
| `500 Server Error` | `INTERNAL_SERVER_ERROR` | Unhandled backend exception (correlation ID logged) |
