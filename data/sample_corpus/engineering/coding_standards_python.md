---
id: eng-python-standards
title: Nimbus Engineering Python 3.11+ Standards and Style Guide
author: Technical Standards Board
version: "2026.0"
doc_status: approved
authority_score: 0.95
owner_group: group_engineering
acl:
  allowed_users: []
  allowed_groups: [group_engineering]
  classification_level: INTERNAL
---

# Python Engineering Standards

## Mandatory Quality Gates
1. **Typing**: Strict `mypy` typing required on all modules. Untyped functions will fail CI gates.
2. **Linting & Formatting**: Ruff for linting and code formatting (`line-length = 100`).
3. **Async IO**: Async everywhere for I/O operations (`asyncio`, `httpx`, `asyncpg`).
4. **Testing**: Minimum 85% test coverage enforced across core domain services.
