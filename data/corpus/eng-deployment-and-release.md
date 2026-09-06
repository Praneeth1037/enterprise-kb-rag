---
doc_id: ENG-002
title: Deployment and Release Management
department: Engineering
sensitivity: internal
owner: platform@northwind-robotics.example
last_updated: 2026-04-25
---

# Deployment and Release Management

## 1. Release Cadence

Services deploy continuously from `main` behind feature flags. Robot firmware follows
a **fortnightly release train** that cuts on alternate Tuesdays at 10:00 Phoenix time.

## 2. Deployment Freeze Windows

Deployments to production are frozen:

- From **December 18 through January 2** inclusive
- During the **last 3 business days of each fiscal quarter**

Freeze exceptions require **VP of Engineering approval** and are limited to Sev1 and
Sev2 fixes. Feature work is never granted a freeze exception.

## 3. Rollback

Any deployment can be rolled back with `nwctl release rollback --service <name>`.
The rollback target is the last known-good revision. **Rollback must complete within
30 minutes** of a Sev1 being declared, or the incident commander switches to a
forward-fix strategy and says so explicitly on the bridge.

## 4. Firmware Specifics

Robot firmware rollbacks are **staged over 24 hours** and cannot be completed in 30
minutes. Fleet-wide firmware issues therefore follow the forward-fix path by default.

## 5. Change Records

Every production deployment writes a change record automatically from CI. Manual
deployments outside CI are prohibited except under the break-glass procedure in
SEC-001.
