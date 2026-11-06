---
id: sales-objection-handling
title: Customer Objection Handling: Security, Hallucinations, and Latency
author: Sales Enablement
version: "2025.3"
doc_status: approved
authority_score: 0.88
owner_group: group_sales
acl:
  allowed_users: []
  allowed_groups: [group_sales]
  classification_level: INTERNAL
---

# Enterprise Objection Handling Guide

## Objection: "How do you prevent data leaks between HR and Engineering?"
**Response**: Nimbus applies pre-retrieval vector-store filters compiled directly from verified JWT claims. A user without HR clearance cannot retrieve HR chunks even if their query is an exact match.
