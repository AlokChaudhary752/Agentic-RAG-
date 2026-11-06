---
id: it-vpn-access
title: WireGuard Zero-Trust Network Access (ZTNA) Architecture
author: Network Security Team
version: "2026.1"
doc_status: approved
authority_score: 0.91
owner_group: group_it
acl:
  allowed_users: []
  allowed_groups: [group_it, group_engineering, group_finance, group_sales]
  classification_level: INTERNAL
---

# Zero-Trust Network Access (ZTNA) Guidelines

Nimbus has decommissioned legacy IPsec/OpenVPN concentrators in favor of Tailscale/WireGuard ZTNA.

## Access Policy
Direct network layer access to production VPCs is eliminated. All developer access to cloud resources occurs via audited ephemeral SSH certificates signed by Nimbus Teleport.
