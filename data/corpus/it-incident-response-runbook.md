---
doc_id: IT-001
title: Production Incident Response Runbook
department: IT
sensitivity: internal
owner: sre@northwind-robotics.example
last_updated: 2026-04-18
---

# Production Incident Response Runbook

## 1. Severity Definitions

| Severity | Definition | Acknowledge SLA | Resolve target |
|----------|------------|-----------------|----------------|
| Sev1 | Customer-facing outage affecting more than 5% of the deployed fleet, or any confirmed data loss | 15 minutes | 4 hours |
| Sev2 | Major feature unavailable, or degradation affecting 1-5% of the fleet | 30 minutes | 1 business day |
| Sev3 | Minor defect with a workaround | 1 business day | 10 business days |

## 2. Paging and Escalation Chain

Alerts page the **primary on-call engineer** through PagerDuty.

1. If the primary does not acknowledge within **15 minutes**, the page auto-escalates
   to the **secondary on-call engineer**.
2. If the secondary does not acknowledge within a further **10 minutes**, the page
   escalates to the **Engineering Manager on duty**.
3. The Engineering Manager on duty escalates to the **VP of Engineering** for any Sev1
   that remains unresolved after **60 minutes**.

Database specialists are on a **separate rotation**. Page them via the
`#dba-oncall` Slack channel or the `dba-primary` PagerDuty schedule. The DBA rotation
does **not** auto-escalate. If the DBA on call is unreachable after two pages, the
incident commander escalates through the **Platform Engineering Manager**, who may
authorise the emergency database access procedure.

> The emergency ("break-glass") production access procedure itself is owned by
> Security and is defined in **SEC-001 Section 6**. This runbook does not grant that
> access; it only tells you who to page.

## 3. Incident Roles

Every Sev1 declares an **Incident Commander (IC)**, a **Communications Lead**, and an
**Operations Lead**. The IC is the most senior responder on the bridge at declaration
time and may delegate the role explicitly.

## 4. Communications

Sev1 incidents require a customer-facing status page update within **30 minutes** of
declaration and every **60 minutes** thereafter until resolution.

## 5. Postmortems

Every Sev1 and Sev2 requires a blameless postmortem published within **5 business days**
of resolution. Action items are tracked in Jira under the `INC` project.
