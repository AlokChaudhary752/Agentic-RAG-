---
id: eng-api-guidelines
title: Nimbus REST & GraphQL API Design Principles
author: API Governance Team
version: "2025.2"
doc_status: approved
authority_score: 0.89
owner_group: group_engineering
acl:
  allowed_users: []
  allowed_groups: [group_engineering]
  classification_level: INTERNAL
---

# API Design Guidelines

All REST endpoints must adhere to semantic versioning (`/api/v1`), enforce ISO 8601 UTC timestamps, and include `X-Correlation-ID` request tracking headers.
