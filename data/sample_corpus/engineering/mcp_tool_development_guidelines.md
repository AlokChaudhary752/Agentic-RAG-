---
id: eng-mcp-tool-guidelines
title: Model Context Protocol (MCP) Tool Development & Safety Guide
author: Agent Platform Team
version: "2026.1"
doc_status: approved
authority_score: 0.96
owner_group: group_engineering
acl:
  allowed_users: []
  allowed_groups: [group_engineering]
  classification_level: INTERNAL
---

# MCP Tool Development Standards

Every tool exposed over MCP must declare a risk tier:
- `read`: Idempotent read-only queries (auto-approved).
- `write_low`: Safe write operations such as creating draft tickets (auto-approved with audit).
- `write_high`: High-risk state changes such as modifying customer records or triggering deployments (mandatory human-in-the-loop approval interrupt).
