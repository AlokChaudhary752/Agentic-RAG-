# API Documentation: Enterprise Knowledge Agent

## Base URL
`/api/v1`

## Authentication
All secured endpoints require an HTTP Bearer JWT token in the `Authorization` header:
```http
Authorization: Bearer <jwt-token>
```

All requests may optionally supply tracing headers:
- `X-Correlation-ID`: Tracing identifier propagated across all logs and downstream calls.
- `X-Tenant-ID`: Tenant scope for multi-tenant isolation (default: `tenant-nimbus-default`).

---

## Endpoints

### 1. Health & Readiness

#### `GET /api/v1/health`
Liveness probe checking that the application is running.
- **Response `200 OK`**:
```json
{
  "status": "healthy",
  "app": "Enterprise Knowledge Agent",
  "environment": "development",
  "timestamp": "2026-11-06T04:15:00.000000Z",
  "version": "0.1.0"
}
```

#### `GET /api/v1/health/ready`
Readiness probe verifying operational state of backing components (Postgres, Qdrant, Redis).
- **Response `200 OK`**:
```json
{
  "ready": true,
  "components": {
    "database": { "status": "healthy", "details": "Operational" },
    "vector_store": { "status": "healthy", "details": "Qdrant pre-filter ready" },
    "cache": { "status": "healthy", "details": "Redis/in-memory cache ready" }
  },
  "timestamp": "2026-11-06T04:15:00.000000Z"
}
```

#### `GET /api/v1/metrics`
Prometheus exposition format for HTTP metrics, query counts, and latency histograms.

---

### 2. Chat & Agent Orchestration (Phase 4)
- `POST /api/v1/chat/completions`: Stateful chat and agent execution.
- `GET /api/v1/chat/stream`: Server-Sent Events (SSE) streaming of agent thought steps and citations.

### 3. Approvals (Phase 5)
- `POST /api/v1/approvals/{task_id}/resolve`: Approve or reject high-risk MCP tool actions.

### 4. Admin & Documents (Phases 1, 3, 7)
- `GET /api/v1/admin/documents`: List ingested documents with ACL metadata.
- `POST /api/v1/admin/sync`: Trigger manual incremental connector synchronization.
- `GET /api/v1/admin/audit`: Query immutable audit events.
