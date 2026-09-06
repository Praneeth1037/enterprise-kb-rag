---
doc_id: SEC-002
title: Data Retention and Deletion Policy
department: Security
sensitivity: internal
owner: privacy@northwind-robotics.example
last_updated: 2026-02-27
---

# Data Retention and Deletion Policy

## 1. Retention Schedule

| Data type | Retention period | System of record |
|-----------|------------------|------------------|
| Application logs | 90 days | Datadog |
| Security audit logs | 400 days | Splunk |
| Customer support tickets | 3 years | Zendesk |
| Employee records | 7 years after termination | Workday |
| Robot telemetry (customer sites) | 13 months | Timescale |
| Recruiting candidate data | 12 months after decision | Greenhouse |

## 2. Deletion Requests

Verified customer deletion requests are completed within **30 calendar days**.
Backups are purged on their own rolling **35-day** cycle, so a record may persist in
backup for up to 35 days after live deletion. This is disclosed in the DPA.

## 3. Legal Hold

A legal hold suspends all deletion for the affected records. Holds are issued by
Legal and released only by Legal.

## 4. Regional Requirements

EU personal data is processed under the standard contractual clauses. Any new vendor
processing EU personal data requires a signed DPA before data is transferred.
