---
id: eng-rag-retrieval-spec
title: Technical Specification: Hybrid Vector & Sparse BM25 Search
author: Lead RAG Architect
version: "2026.1"
doc_status: approved
authority_score: 0.97
owner_group: group_engineering
acl:
  allowed_users: []
  allowed_groups: [group_engineering]
  classification_level: INTERNAL
---

# RAG Hybrid Retrieval Specification

Retrieval combines dense semantic embeddings (BAAI/bge-m3) with sparse lexical tokens using Reciprocal Rank Fusion (RRF, k=60). ACL filters are strictly compiled into Qdrant HNSW payloads prior to nearest neighbor traversal.
