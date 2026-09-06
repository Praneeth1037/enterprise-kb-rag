---
doc_id: SEC-001
title: Information Security Policy
department: Security
sensitivity: internal
owner: security@northwind-robotics.example
last_updated: 2026-04-02
---

# Information Security Policy

## 1. Scope

This policy applies to all employees, contractors, and third parties with access to
Northwind Robotics systems.

## 2. Authentication

Multi-factor authentication is mandatory on all systems. Hardware security keys
(FIDO2) are required for anyone with production access. SMS one-time codes are
**not** an accepted second factor.

## 3. Data Classification

| Class | Examples | Handling |
|-------|----------|----------|
| Public | Marketing material, published docs | No restriction |
| Internal | Runbooks, handbooks, policies | Employees and contractors |
| Confidential | Compensation data, unreleased financials, customer PII | Named audience only; contractors excluded |
| Restricted | Signing keys, security incident detail, M&A material | Explicit grant, logged access |

## 4. Access Control

Access follows least privilege and is reviewed **quarterly**. Standing write access to
production databases is **not granted to any individual account**. Disclosure of
Confidential material outside its named audience is a policy violation and is handled
under the disciplinary process.

## 5. Endpoint Requirements

Full-disk encryption, the managed EDR agent, and automatic OS updates are required on
every device. Devices out of compliance for more than **14 days** are blocked from SSO.

## 6. Emergency Production Access (Break-Glass)

When an incident cannot be resolved without direct production database access, the
break-glass procedure applies:

1. The Incident Commander files a break-glass request in the vault, naming the incident
   ID and the specific database.
2. The request requires **two approvals: the on-call Engineering Manager and the
   Security Duty Officer**. Both approvals are required; neither may approve alone,
   and self-approval is rejected.
3. On approval, the vault issues a **time-boxed credential valid for 4 hours**. It
   cannot be extended; a second request must be filed instead.
4. The entire session is **recorded and streamed to the security audit log**.
5. A **break-glass review is held within 3 business days** of the incident, chaired by
   the Security Duty Officer, and the recording is reviewed line by line.

The Security Duty Officer is reachable 24/7 via the `security-duty` PagerDuty schedule.

## 7. Reporting

Suspected incidents are reported to `security@northwind-robotics.example` or
`#security-report` **within 1 hour** of discovery.
