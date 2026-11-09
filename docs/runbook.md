# Enterprise Knowledge Agent: Operational Runbook

> Production operations guide, local deployment instructions, incident response playbooks, and backup/restore procedures.

---

## 1. System Requirements & Architecture Stack

| Subsystem | Technology | Port | Notes |
|---|---|---|---|
| **API Gateway & Agent** | FastAPI (Python 3.12) | `8000` | Hexagonal architecture, LangGraph |
| **Frontend UI** | Next.js 14, React, Tailwind | `3000` | Chat, Citations Drawer, Admin Console |
| **Relational Database** | PostgreSQL 16 | `5432` | Users, ACLs, Document metadata, Audit trail |
| **Vector Database** | Qdrant | `6333` | HNSW with native ACL pre-filtering |
| **Cache & Limiter** | Redis 7 | `6379` | Semantic cache & sliding-window rate limit |
| **Telemetry & Metrics** | Prometheus | `9090` | Scrapes `/api/v1/metrics` |
| **Dashboards** | Grafana | `3002` | Pre-provisioned RAG observability dashboards |

---

## 2. Quickstart Deployment Guide

### Option A: Single-Command Docker Compose Deployment (Recommended)
```bash
# 1. Clone the repository
git clone https://github.com/AlokChaudhary752/Agentic-RAG-.git
cd Agentic-RAG-

# 2. Launch the complete containerized stack
docker compose up -d

# 3. Verify services are healthy
curl -s http://localhost:8000/api/v1/health | jq
curl -s http://localhost:8000/api/v1/health/ready | jq

# 4. Open applications in browser:
#    - Web Application:   http://localhost:3000
#    - Admin Dashboard:   http://localhost:3000/admin
#    - Prometheus:        http://localhost:9090
#    - Grafana:           http://localhost:3002 (admin / admin)
```

### Option B: Local Developer Mode (Bare Metal)
```bash
# 1. Install backend dependencies
python -m pip install -e ".[dev]"

# 2. Run unit and integration test suite
python -m pytest backend/tests

# 3. Seed PostgreSQL schema and sample corpus
$env:PYTHONPATH="backend"
python scripts/seed_data.py

# 4. Start backend server
python -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000 --reload

# 5. In a separate terminal, install and start Next.js frontend
cd frontend
npm install
npm run dev
# App will be accessible at http://localhost:3000
```

---

## 3. Interactive CLI Demonstration (`scripts/demo.py`)

To verify the three headline capabilities from the command line:
```bash
# Run all 3 scenarios automatically:
python scripts/demo.py

# Or run interactively with pauses between scenarios:
python scripts/demo.py --interactive

# Or run a specific scenario:
python scripts/demo.py --scenario 1  # Permission Isolation (Alice vs. Bob)
python scripts/demo.py --scenario 2  # Conflict Resolution ($125 approved vs $75 deprecated)
python scripts/demo.py --scenario 3  # Human-in-the-Loop MCP Jira creation
```

---

## 4. Configuration & Environment Variables

All configuration is centralized in `backend/app/core/config.py` using `pydantic-settings`:

| Variable | Default Value | Description |
|---|---|---|
| `APP_ENV` | `development` | `development`, `test`, `production` |
| `APP_PORT` | `8000` | Port for FastAPI HTTP server |
| `DATABASE_URL` | `sqlite+aiosqlite:///./enterprise_agent.db` | PostgreSQL connection string |
| `QDRANT_HOST` | `localhost` | Qdrant service hostname |
| `QDRANT_PORT` | `6333` | Qdrant gRPC/HTTP port |
| `QDRANT_USE_IN_MEMORY` | `false` | Fall back to embedded in-memory Qdrant |
| `REDIS_URL` | `redis://localhost:6379/0` | Redis caching & rate limiting endpoint |
| `JWT_SECRET_KEY` | `dev-insecure-jwt-secret...` | Secret key for HMAC-SHA256 JWT signing |
| `RATE_LIMIT_USER_RPM` | `30` | Max requests per minute per user |
| `RATE_LIMIT_TENANT_RPM` | `100` | Max requests per minute per tenant |
| `AGENT_BUDGET_USD_QUERY`| `0.15` | Spend cap in USD per agent reasoning cycle |

---

## 5. Verification & Quality Gates

Run all quality and regression gates prior to production deployment:

```bash
# 1. Linting & Formatting Check
ruff check backend/ frontend/

# 2. Strict Type Checking
mypy backend/app

# 3. Unit, Integration, & Security Test Suite
python -m pytest backend/tests -v

# 4. Code Coverage Verification (Must exceed 85%)
python -m pytest backend/tests --cov=app --cov-report=term-missing

# 5. RAGAS Empirical Benchmark & Regression Gate
python evaluation/run_eval.py
```

---

## 6. Incident Response & Troubleshooting Playbooks

### Playbook 1: Zero Permission Leak Alert (`P0`)
- **Condition**: Prometheus alert `ZeroPermissionLeakDetected` fires (`rag_permission_leaks_total > 0`).
- **Impact**: An unauthorized document chunk was intercepted by the secondary defense assertion.
- **Triage Steps**:
  1. Inspect PostgreSQL audit logs:
     ```sql
     SELECT * FROM audit_logs WHERE severity = 'SECURITY_ALERT' ORDER BY created_at DESC LIMIT 10;
     ```
  2. Identify the offending `chunk_id`, calling `user_id`, and query.
  3. Verify Qdrant payload index for that chunk:
     Ensure `acl.allowed_users`, `acl.allowed_groups`, and `acl.classification_level` match PostgreSQL metadata.
  4. If out of sync, trigger manual connector re-indexing:
     ```bash
     python scripts/seed_data.py
     ```

### Playbook 2: Rate Limit 429 Flood (`P2`)
- **Condition**: Spike in HTTP 429 responses.
- **Impact**: Legitimate users unable to send queries.
- **Triage Steps**:
  1. Inspect Prometheus metric `rate_limit_exceeded_total` grouped by `user_id` and `tenant_id`.
  2. If a batch script or scraper is responsible, verify its API token.
  3. Temporarily raise per-user limits by updating `RATE_LIMIT_USER_RPM` in environment or Redis config.

### Playbook 3: Qdrant Vector Store Connection Failure (`P1`)
- **Condition**: Logs report `Live Qdrant service unreachable, initializing in-memory Qdrant fallback`.
- **Impact**: System falls back to in-memory mode, which indexes on startup but does not persist across container restarts.
- **Resolution**:
  ```bash
  docker compose restart qdrant
  curl http://localhost:6333/collections
  ```

### Playbook 4: Database Backup & Restore
```bash
# Backup PostgreSQL database
docker compose exec postgres pg_dump -U postgres enterprise_agent > backup_$(date +%Y%m%d).sql

# Restore PostgreSQL database
cat backup_20261109.sql | docker compose exec -T postgres psql -U postgres enterprise_agent
```
