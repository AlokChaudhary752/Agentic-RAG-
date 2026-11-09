# Enterprise Knowledge Agent: STRIDE Threat Model & Security Architecture

> Comprehensive security threat analysis following Microsoft STRIDE methodology for the **Enterprise Knowledge Agent** platform.

---

## 1. System Assets, Boundaries & Threat Actors

### 1.1 Protected Assets
- **Confidential Knowledge Assets**: Executive compensation schedules, board minutes, unannounced corporate acquisitions, engineering trade secrets, security audit findings.
- **Identity & Authorization Tokens**: Asymmetric/HMAC JWT tokens, user clearance records, group memberships.
- **Customer & Employee PII**: Social security numbers, compensation figures, home addresses, personal phone numbers, banking details.
- **Execution Credentials**: Jira API tokens, corporate email relay credentials, vector store API keys.
- **Audit Trails**: Immutable logs documenting retrieved chunk IDs, user identifiers, timestamp hashes, and tool approvals.

### 1.2 Threat Actors & Trust Boundaries
- **Untrusted Employee (Insider Threat)**: Authenticated user with valid corporate credentials attempting to access documents exceeding their clearance (e.g. employee attempting to read salary bands).
- **Compromised Account**: Legitimate credential pair stolen by an external attacker.
- **Adversarial Document Author**: Attacker who injects malicious prompt injection payloads into documents ingested by connectors (Google Drive, Confluence, Slack).
- **Unauthorized Tool Caller**: Malicious actor attempting to invoke high-risk MCP actions without proper role or approval.

---

## 2. STRIDE Threat Analysis Matrix

| Threat Category | Potential Attack Vector | Impact | Platform Mitigation Strategy | Verification / Test |
|---|---|---|---|---|
| **S** - *Spoofing* | Attacker forges Bearer JWT claiming executive role or manipulates `user_id` claim in HTTP header. | Unauthorized access to confidential documents. | - Cryptographic signature verification using HMAC-SHA256 with rotatable secret.<br/>- Token expiration enforcement (default 60 mins).<br/>- Re-verification of user existence and active status against PostgreSQL `UserRepository`. | `test_security.py::test_invalid_signature_raises_unauthorized`, `test_expired_token_raises_unauthorized` |
| **T** - *Tampering* | 1. Direct tampering with ingested document text or metadata.<br/>2. Indirect prompt injection embedded in documents attempting to hijack system prompts. | Hijacked agent behavior, unauthorized actions executed, misinformation. | - Cryptographic SHA-256 chunk hashing and immutable storage in relational DB.<br/>- `PromptInjectionDefense` engine scanning queries and chunks for adversarial patterns (`ignore previous instructions`, `system override`, `exfiltrate`).<br/>- Strict XML document bounding tags (`<context>...</context>`). | `test_prompt_injection.py::test_detect_ignore_instructions_pattern`, `test_injection_defense_flags_risk` |
| **R** - *Repudiation* | Employee retrieves restricted M&A document or creates disruptive Jira ticket, then denies the action. | Inability to audit security incidents or prove non-compliance. | - Immutable, append-only PostgreSQL `audit_logs` table recording `user_id`, `query_hash`, `retrieved_chunk_ids`, `mcp_action`, `ip_address`, and `correlation_id`.<br/>- Content of confidential documents is never logged in plaintext; only document and chunk IDs are retained. | `test_audit_service.py::test_audit_event_logging`, `test_audit_log_querying` |
| **I** - *Information Disclosure* | **Permission Leaks**: Employee with `INTERNAL` clearance queries executive salary tables or board minutes. Cross-user semantic cache leakage. | Critical breach of enterprise confidentiality, legal non-compliance (GDPR, SOC 2). | - **Vector-Level ACL Pre-Filtering**: Qdrant HNSW vector graph traversal strictly filters candidates matching `(allowed_users OR allowed_groups) AND (clearance <= user_clearance)`.<br/>- **Defense-in-Depth Assertion**: In-memory validator re-asserts all chunks against caller `UserPrincipal` before generation. Fails closed on any discrepancy.<br/>- **ACL-Scoped Cache Partitioning**: Cache keys incorporate MD5 of query + tenant + clearance + sorted groups.<br/>- **PII Masking**: Presidio PII redaction during ingestion. | `test_security.py`, `test_qdrant_acl_pre_filtering.py`, `test_semantic_cache.py::test_acl_scoped_cache_key_isolation`, Golden QA benchmark regression gate (0.0% leak rate). |
| **D** - *Denial of Service* | 1. Malicious user floods `/api/v1/chat/completions` with rapid queries.<br/>2. Recursive prompt causing unbounded LangGraph agent execution loops.<br/>3. Adversarial query exhausting LLM token budget. | API unresponsiveness, excessive cloud infrastructure and LLM token costs. | - **Multi-Tenant Sliding Window Rate Limiting**: Per-user (30 req/min) and per-tenant (100 req/min) sliding window limits with Redis/memory fallback injecting `X-RateLimit-*` headers.<br/>- **Graph Recursion Limit**: LangGraph cycle limit set to max 2 retrieval iterations.<br/>- **Token & Cost Budgets**: Hard query spend cap (`agent_budget_usd_per_query: $0.15`) monitored by `CostTracker`. | `test_rate_limiter.py::test_rate_limit_per_user_exceeded`, `test_cost_tracker.py::test_query_cost_budget_enforcement` |
| **E** - *Elevation of Privilege* | Low-clearance employee commands agent to file executive Jira ticket or delete/reconfigure enterprise data. | Unauthorized enterprise state mutation via MCP tools. | - **Tool Risk Tiering**: Every MCP tool classified as `read`, `write_low`, or `write_high`.<br/>- **Mandatory Human-in-the-Loop Gate**: All `write_high` tools (e.g. `create_jira_ticket`) pause execution and require explicit approval.<br/>- **Caller Role & Group Check**: MCP client checks user group membership before executing even approved actions.<br/>- **Idempotency Safeguard**: Client-side idempotency cache prevents duplicate action replay. | `test_mcp_client.py::test_mcp_client_human_approval_gate_for_write_high`, `test_agent_mcp_tool_execution.py` |

---

## 3. Defense-in-Depth Implementation Details

### 3.1 Primary Vector Pre-Filtering (Qdrant)
Pre-filtering is implemented directly in Qdrant's payload index filter:
```python
# Executed natively in Qdrant before vector distance computation
qfilter = qmodels.Filter(
    must=[
        qmodels.Filter(
            should=[
                qmodels.FieldCondition(key="acl.allowed_users", match=qmodels.MatchValue(value=principal.user_id)),
                qmodels.FieldCondition(key="acl.allowed_groups", match=qmodels.MatchAny(any=principal.groups)),
            ]
        ),
        qmodels.FieldCondition(
            key="acl.classification_level",
            match=qmodels.MatchAny(any=[c.value for c in authorized_levels]),
        ),
    ]
)
```

### 3.2 Secondary In-Memory Assertion (Defense-in-Depth)
Before candidate chunks are passed to answer synthesis, `ACLAssertionValidator` scans every retrieved chunk:
```python
for chunk in candidates:
    if not is_authorized(chunk.acl, principal):
        logger.critical(
            "PERMISSION LEAK DETECTED",
            user_id=principal.user_id,
            chunk_id=chunk.id,
            doc_id=chunk.doc_id,
        )
        # Increment Prometheus telemetry counter
        RAG_PERMISSION_LEAKS_TOTAL.labels(tenant_id=principal.tenant_id).inc()
        # Fail closed immediately
        raise PermissionLeakError(f"Access violation: User '{principal.user_id}' cannot view chunk '{chunk.id}'")
```

### 3.3 Semantic Cache ACL Partitioning
The semantic cache key is derived as:
$$\text{CacheKey} = \text{MD5}(\text{Query} + \text{TenantID} + \text{Clearance} + \text{SortedGroups})$$
This ensures that two employees asking the exact same question receive isolated cached answers matching their respective clearances.

---

## 4. Security Incident Response & Alerting Playbook

1. **Permission Leak Event**:
   - **Trigger**: `RAG_PERMISSION_LEAKS_TOTAL > 0`
   - **Severity**: P0 / Critical
   - **Automated Action**: Immediate request abort (HTTP 403), audit event logged with `severity='SECURITY_ALERT'`.
   - **Triage Action**: Inspect PostgreSQL `audit_logs` for `user_id` and `chunk_id`. Verify Qdrant payload index integrity.

2. **High Prompt Injection Score**:
   - **Trigger**: Query injection risk score $\ge 0.7$
   - **Severity**: P2 / Warning
   - **Automated Action**: Strip adversarial prompt overrides and log warning.

3. **Rate Limit Flood**:
   - **Trigger**: Multiple HTTP 429 responses from a single IP or user account within 1 minute.
   - **Severity**: P3 / Operational
   - **Automated Action**: Temporary IP/user throttle enforced by Redis sliding window counter.
