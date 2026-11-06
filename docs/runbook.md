# Enterprise Knowledge Agent: Operational Runbook

## 1. Quick Start & Execution

### Option A: Local Development Mode (No Docker Required)
```bash
# 1. Install dependencies
uv --no-config pip install --python .venv/Scripts/python.exe -e ".[dev]"

# 2. Run unit tests
.venv/Scripts/pytest backend/tests/unit

# 3. Start backend API server
.venv/Scripts/uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000 --reload
```

### Option B: Docker Compose
```bash
# Start all infrastructure (Postgres, Qdrant, Redis, Langfuse, Backend, Frontend)
docker compose up -d

# Verify health
curl -s http://localhost:8000/api/v1/health | jq
```

## 2. Ingestion & Indexing
To seed synthetic corporate knowledge and index documents into Qdrant & PostgreSQL:
```bash
python scripts/seed_data.py
```

## 3. Running Regression & Security Verification
```bash
# Run permission leak security test suite (Zero-leak verification)
pytest backend/tests/security -v

# Run RAGAS benchmark evaluation
python evaluation/run_eval.py
```

## 4. Troubleshooting
- **Database Connection Refused**: Verify PostgreSQL is running on port 5432 or configure SQLite fallback `DATABASE_URL=sqlite+aiosqlite:///./enterprise_agent.db`.
- **Qdrant Port Conflict**: Ensure Qdrant is available on 6333 or set `QDRANT_USE_IN_MEMORY=true` for local embedded operation.
- **Permission Leak Alert**: If a `PermissionLeakError` is logged, examine the audit trail in PostgreSQL table `audit_logs` where `severity = 'SECURITY_ALERT'`.
