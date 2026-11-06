---
id: it-password-policy-2026
title: Nimbus Identity, Passkey, and Authentication Standard 2026
author: Information Security Director
version: "2026.1"
doc_status: approved
authority_score: 0.97
owner_group: group_it
acl:
  allowed_users: []
  allowed_groups: [group_it, group_engineering, group_hr, group_finance, group_sales, group_legal]
  classification_level: INTERNAL
---

# Nimbus Identity and Passkey Authentication Standard 2026

> This is the ACTIVE and AUTHORITATIVE authentication standard across Nimbus Technologies.

## Elimination of Periodic Password Expiry
Following NIST SP 800-63B guidelines, **periodic 90-day password rotation is strictly abolished**. Mandatory password changes only occur upon confirmed or suspected compromise.

## Passphrase & FIDO2 Passkey Mandate
1. Passkeys (FIDO2 WebAuthn / YubiKey) are required for all privileged accounts (Engineers, Admins, Finance).
2. For legacy applications requiring passwords, minimum passphrase length is **16 characters**. Arbitrary symbol complexity rules are replaced with length-based entropy checks.

## MFA Enforcement
All corporate logins require hardware-backed MFA or Okta FastPass. SMS-based OTP is prohibited due to SIM-swap vulnerabilities.
