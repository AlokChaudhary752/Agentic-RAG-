---
id: eng-db-migrations
title: Zero-Downtime Database Migration Guidelines & Alembic Standards
author: Data Platform Team
version: "2025.3"
doc_status: approved
authority_score: 0.91
owner_group: group_engineering
acl:
  allowed_users: []
  allowed_groups: [group_engineering]
  classification_level: INTERNAL
---

# Zero-Downtime Database Migration Protocol

All database schema evolutions must support backwards compatibility with current running backend replicas. Column deletions require a two-phase rollout: first make column nullable and deprecate in code, then remove column in subsequent sprint.
