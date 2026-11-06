# ADR 0001: Selection of Qdrant as Core Vector Database

## Status
Accepted

## Date
2026-11-06

## Context
The Enterprise Knowledge Agent requires a high-performance vector search engine supporting:
1. Hybrid search (dense semantic embeddings + sparse BM25/SPLADE lexical representations).
2. Native payload-level filtering executed before nearest neighbor graph traversal to enforce zero-leak Access Control Lists (ACLs).
3. Local development and test ergonomics (in-memory mode for CI and local unit/integration tests without hard cloud dependencies).
4. Enterprise scale, multi-tenancy isolation (`tenant_id`), and high concurrency.

## Decision
We adopt **Qdrant** (v1.11+) as the primary vector storage and retrieval engine, utilizing payload schemas with indexed ACL fields (`allowed_users`, `allowed_groups`, `classification_level`, `tenant_id`).

## Rationale
- **Qdrant**: Native support for hybrid dense + sparse vectors in a single collection. Native pre-filtering using HNSW payload index, avoiding post-filtering recall loss. Offers an in-memory client (`:memory:`) enabling sub-millisecond execution in automated unit and CI pipelines.
- **pgvector (Discarded for Vector Primary)**: Excellent for relational joins, but indexing large dense + sparse vectors at scale with complex boolean ACL combinations creates significant database CPU pressure compared to dedicated Rust-based vector engines. We retain PostgreSQL for relational entities, audit logs, and ACL definitions.
- **Milvus / Pinecone (Discarded)**: Pinecone lacks self-hosted/offline local execution. Milvus introduces substantial operational overhead (etcd, Pulsar/Kafka, MinIO dependencies) that impedes local single-command developer startup.

## Consequences
### Positive
- Sub-50ms hybrid retrieval with guaranteed pre-filtered ACL evaluation.
- Local tests can run fully offline without external containers via Qdrant's embedded/in-memory mode.
- Reciprocal Rank Fusion (RRF) natively supported across dense and sparse queries.

### Negative / Trade-offs
- Requires maintaining synchronization between PostgreSQL (source of truth for users, documents, permissions) and Qdrant payloads.

### Mitigations
- Document ingestion pipeline runs transactional or idempotent updates, upserting to both PostgreSQL and Qdrant with content hash checks and deletion tracking.

