---
id: eng-data-classification
title: Data Classification, Tagging and Schema Standards
author: Data Governance
version: "2025.1"
doc_status: approved
authority_score: 0.90
owner_group: group_engineering
acl:
  allowed_users: []
  allowed_groups: [group_engineering, group_security]
  classification_level: INTERNAL
---

# Data Classification Technical Standards

All Kafka events, Postgres tables, and S3 objects must carry mandatory classification tags: `public`, `internal`, `confidential`, or `restricted`.
