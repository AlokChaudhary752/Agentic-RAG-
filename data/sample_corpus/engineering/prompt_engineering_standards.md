---
id: eng-prompt-standards
title: Enterprise LLM Prompt Engineering & Versioning Standards
author: AI Research Group
version: "2026.0"
doc_status: approved
authority_score: 0.94
owner_group: group_engineering
acl:
  allowed_users: []
  allowed_groups: [group_engineering]
  classification_level: INTERNAL
---

# Prompt Engineering & System Instructions

## Rules for AI Prompt Authoring
1. System prompts must never be hard-coded into application logic; they reside in version-controlled markdown files under `prompts/`.
2. All retrieved context must be enclosed in clear untrusted data delimiters (e.g. `<context>...</context>`).
3. Prompts must explicitly instruct models to abstain ("I do not have sufficient information") rather than fabricate unverified claims.
