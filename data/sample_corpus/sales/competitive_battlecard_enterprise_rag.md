---
id: sales-battlecard-rag
title: Competitive Battlecard: Nimbus vs. Legacy Naive RAG Systems
author: Product Marketing
version: "2026.1"
doc_status: approved
authority_score: 0.91
owner_group: group_sales
acl:
  allowed_users: []
  allowed_groups: [group_sales]
  classification_level: INTERNAL
---

# Competitive Battlecard: Nimbus vs. Generic Naive RAG

## Our Key Differentiators
1. **Zero Permission Leaks**: Pre-filtering inside Qdrant HNSW traversal ensures employees never see unauthorized chunks. Generic RAG relies on post-filtering or has zero ACL awareness.
2. **Conflict Resolution**: When 2024 and 2026 policies conflict, Nimbus detects near-duplicates and prefers the newer, approved source while warning the user.
3. **Safe MCP Action Execution**: High-risk tool calls pause for human approval.
