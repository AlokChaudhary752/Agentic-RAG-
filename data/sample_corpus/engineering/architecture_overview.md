---
id: eng-arch-overview
title: Nimbus Cloud Platform Architecture Overview & Microservices Topology
author: Principal Architecture Committee
version: "2026.1"
doc_status: approved
authority_score: 0.96
owner_group: group_engineering
acl:
  allowed_users: []
  allowed_groups: [group_engineering, group_managers]
  classification_level: INTERNAL
---

# Nimbus Cloud Platform Architecture

## Core Technology Stack
- **Languages**: Python 3.12 (AI/Data pipelines), Go 1.23 (High-throughput gateway), TypeScript/React (UI).
- **Orchestration**: Kubernetes on AWS EKS with Karpenter autoscaling.
- **Databases**: PostgreSQL (Aurora Multi-AZ), Redis Cluster, Qdrant Vector Engine.
- **Messaging**: Apache Kafka for event-driven telemetry and asynchronous document ingestion.
