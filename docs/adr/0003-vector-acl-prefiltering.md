# ADR 0003: Vector-Store-Level ACL Pre-Filtering and Defense-in-Depth

## Status
Accepted

## Date
2026-11-06

## Context
In an enterprise multi-user RAG system, documents have strict access controls (e.g. Executive only, HR only, Finance only). A naive implementation retrieves the top-$K$ semantic matches and then discards documents the user is not permitted to see (post-filtering). This approach suffers from two severe flaws:
1. **Security / Information Leak Risk**: If a post-filtering assertion fails or has bugs, unauthorized text passes to the LLM context.
2. **Recall Starvation**: If the top-$K$ most semantically similar documents are confidential to other departments, post-filtering removes them all, leaving 0 relevant results even though valid authorized documents exist at rank $K+1 \dots 2K$.

## Decision
We enforce **ACL Pre-Filtering directly inside the vector engine index query**, supplemented with a **post-retrieval defense-in-depth assertion**:
1. When a user authenticates, their User ID, direct permissions, and group memberships are resolved from their verified JWT and PostgreSQL identity store.
2. A boolean filter clause is compiled into the native Qdrant query filter:
   - `tenant_id == user.tenant_id`
   - `allowed_users CONTAINS user.id` OR `allowed_groups INTERSECTS user.groups` OR `classification_level <= user.clearance`
3. Nearest-neighbor graph traversal (HNSW) only visits vectors matching this filter.
4. **Defense-in-Depth**: A mandatory secondary post-retrieval validator inspects every retrieved chunk. If any chunk does not satisfy the calling user's ACL, the pipeline immediately halts, aborts the LLM synthesis, logs a high-severity security audit alert, and fails closed.

## Rationale
- Guaranteed zero-leak security boundary.
- Elimination of recall starvation caused by post-hoc discarding.
- Defense-in-depth prevents accidental leaks even if the database index configuration is tampered with.

## Consequences
### Positive
- Zero permission leaks across automated permission matrix tests.
- Optimal retrieval recall regardless of how many restricted documents share similar vocabulary.

### Negative / Trade-offs
- Payload filtering requires index fields (`allowed_groups`, `allowed_users`, `tenant_id`) to be indexed in Qdrant memory.

### Mitigations
- Schema creation scripts explicitly mark ACL fields as keyword payload indexes.
