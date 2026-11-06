---
id: it-dr-runbook
title: IT Disaster Recovery and Backup Restoration Protocol
author: IT Infrastructure Team
version: "2026.0"
doc_status: approved
authority_score: 0.94
owner_group: group_it
acl:
  allowed_users: []
  allowed_groups: [group_it, group_engineering]
  classification_level: CONFIDENTIAL
---

# IT Disaster Recovery and Business Continuity

## Backup Schedule
- Databases: Continuous WAL archiving to S3 multi-region with daily point-in-time snapshots.
- Code repositories: Synchronized across GitHub Enterprise and secondary cold AWS replica.

## RPO & RTO Objectives
- **Recovery Point Objective (RPO)**: <= 5 minutes of transactional data.
- **Recovery Time Objective (RTO)**: <= 60 minutes for core API workloads.
