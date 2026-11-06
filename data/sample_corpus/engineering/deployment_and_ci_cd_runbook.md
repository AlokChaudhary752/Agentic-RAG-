---
id: eng-cicd-runbook
title: Continuous Integration & Deployment Pipeline Runbook
author: Release Engineering
version: "2026.1"
doc_status: approved
authority_score: 0.93
owner_group: group_engineering
acl:
  allowed_users: []
  allowed_groups: [group_engineering]
  classification_level: INTERNAL
---

# CI/CD Deployment Runbook

Deployments use ArgoCD with automated canary rollouts (10% traffic for 15 minutes, automated rollback on error rate exceeding 0.5%).
