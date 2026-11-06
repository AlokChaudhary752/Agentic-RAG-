# Enterprise Knowledge Agent: STRIDE Threat Model

This document outlines the security architecture and STRIDE threat analysis for the **Enterprise Knowledge Agent**.

## 1. System Scope & Assets
- **Protected Assets**: Confidential enterprise documents, salary tables, legal agreements, employee PII, audit trails, MCP execution credentials.
- **Threat Actors**: Malicious employees (insider threats), compromised user accounts, external prompt injection attacks embedded in scanned/parsed documents, unauthorized tool callers.

## 2. STRIDE Analysis Matrix

| Threat Category | Potential Vector | Mitigation in Enterprise Knowledge Agent |
|---|---|---|
| **Spoofing** | Attacker crafts forged JWT or impersonates an executive user. | Cryptographically verified asymmetric/HMAC JWT tokens signed with secret key; mandatory user identity validation before graph initialization; user context bound per request. |
| **Tampering** | Ingestion pipeline tampering or modifying document permissions. | Cryptographic hashing of document contents; immutable ACL records in PostgreSQL; transactional synchronization between relational store and Qdrant payloads. |
| **Repudiation** | User denies performing an action or retrieving classified documents. | Immutable, append-only audit trail logging `user_id`, query hash, retrieved chunk IDs (no classified content logged), tool invocations, and human approvals. |
| **Information Disclosure** | User with employee-level clearance queries salary bands or executive memos. | **ACL Pre-Filtering at the vector store index level** prevents unauthorized vectors from ever entering candidate sets; **Defense-in-Depth secondary assertion** fails closed if any chunk violates user ACL; semantic cache is ACL-partitioned. |
| **Denial of Service** | Complex recursive queries or adversarial token-exhaustion loops. | Per-user rate limiting (Redis token bucket); per-query hard execution timeouts (45s); LangGraph loop recursion limits (max 5 iterations); maximum USD cost budgets per query. |
| **Elevation of Privilege** | Indirect prompt injection in documents attempting to trigger high-risk MCP tools. | Untrusted document wrapping with XML boundaries; strict separation between instructions and retrieved data; human-in-the-loop approval interrupt for `write_high` MCP tools (e.g. Jira modifications); tool allow-lists checked against user roles. |

## 3. Defense-in-Depth Guarantee
1. **Pre-Filter**: Enforced inside Qdrant HNSW vector traversal.
2. **Post-Assertion**: In-memory verification of every candidate payload against the calling user's principal before LLM synthesis.
3. **Audit Trigger**: Immediate high-severity alert logged if the secondary assertion intercepts an unauthorized chunk.

