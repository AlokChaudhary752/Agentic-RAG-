---
id: it-incident-sla-2026
title: IT Support & Incident Response Service Level Agreements (SLA)
author: IT Operations
version: "2026.1"
doc_status: approved
authority_score: 0.95
owner_group: group_it
acl:
  allowed_users: []
  allowed_groups: [group_it, group_engineering, group_managers]
  classification_level: INTERNAL
---

# IT Service Level Agreements & Incident Response Matrix

## Incident Priority Tiers & Response Expectations

| Severity Level | Definition | First Response SLA | Target Resolution SLA | Escalation Target |
|---|---|---|---|---|
| P0 - Critical Emergency | Entire datacenter down, data breach, customer-facing outage | 15 minutes | 2 hours | VP of Engineering & CTO |
| P1 - Major Degradation | Core service degraded, entire department blocked | 30 minutes | 4 hours | IT Ops Director |
| P2 - Moderate Incident | Single system issue with viable manual workaround | 2 hours | 1 business day | IT Team Lead |
| P3 - Minor / Request | Laptop accessories, software license provisioning | 8 business hours | 3 business days | Helpdesk Tier 1 |

## On-Call Escalation Hotline
Critical P0 events automatically trigger PagerDuty rotation on-call engineer at +1-800-555-NIMBUS-OPS.
