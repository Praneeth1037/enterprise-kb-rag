---
doc_id: IT-002
title: IT Onboarding, Accounts and Equipment
department: IT
sensitivity: internal
owner: it-helpdesk@northwind-robotics.example
last_updated: 2026-03-14
---

# IT Onboarding, Accounts and Equipment

## 1. Day One Accounts

Okta SSO, Google Workspace, Slack, and Jira accounts are provisioned automatically
from the Workday record **2 business days before the start date**. If accounts are
missing on day one, file a `IT-ONBOARD` ticket; the helpdesk SLA is **4 business hours**.

## 2. Hardware Tiers

| Tier | Specification | Eligibility | Approver |
|------|---------------|-------------|----------|
| Standard | 14" laptop, M-series, 16 GB RAM, 512 GB SSD | All employees and contractors | Automatic |
| Plus | 16" laptop, M-series Pro, 32 GB RAM, 1 TB SSD | ML, simulation, and CAD roles only | **Director approval required** |
| Workstation | Desktop, 64 GB RAM, discrete GPU | Robotics perception team, on request | Director + IT approval |

Plus tier requests are filed as `IT-HW-UPGRADE` tickets and must name the approving
Director. Requests without a named Director approver are rejected automatically.

## 3. Shipping and Collection

Hardware for employees ships to the home address on file. **Hardware for contractors
and contingent workers must ship to a Northwind office and be collected in person**,
with badge verification at pickup. This applies in all jurisdictions and exists so that
asset custody is recorded against a badge ID.

The Berlin office receives hardware shipments on **Tuesdays and Thursdays** only.

## 4. Return

All hardware is returned on or before the last working day. Unreturned hardware is
reported to People Ops after **10 business days**.

## 5. Software Installation

Employees may self-install software from the Okta app catalogue. Anything outside the
catalogue requires a Security review; see FIN-002 for purchase thresholds.
