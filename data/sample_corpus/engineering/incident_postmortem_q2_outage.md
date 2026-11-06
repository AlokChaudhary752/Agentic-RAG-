---
id: eng-postmortem-q2-outage
title: Post-Mortem Report: Incident #4082 Redis Sentinel Partition Outage
author: Reliability Task Force
version: "1.0"
doc_status: approved
authority_score: 0.90
owner_group: group_engineering
acl:
  allowed_users: []
  allowed_groups: [group_engineering, group_managers]
  classification_level: INTERNAL
---

# Post-Mortem Incident #4082: Redis Sentinel Split-Brain

On May 14, 2025, a network partition between AWS Availability Zones us-east-1a and us-east-1b caused a split-brain election in Redis Sentinel, causing 42 minutes of degraded query caching. Action item completed: Migrated to Redis Cluster with multi-master quorum.
