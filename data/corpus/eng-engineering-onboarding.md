---
doc_id: ENG-001
title: Engineering Onboarding Guide
department: Engineering
sensitivity: internal
owner: platform@northwind-robotics.example
last_updated: 2026-03-30
---

# Engineering Onboarding Guide

## 1. Local Environment

All services build with `make bootstrap`, which installs the pinned toolchain
(Python 3.11, Go 1.23, Node 20) through `mise`. The monorepo is `northwind/core`.
A full clean build takes roughly **12 minutes** on Standard tier hardware.

## 2. Repository Layout

- `platform/` - shared infrastructure, service mesh, auth
- `fleet/` - robot fleet management APIs
- `perception/` - vision and sensor fusion
- `console/` - customer-facing web console

## 3. Code Review

Every change lands through a pull request. **Changes under `platform/` require 2
approvals; all other paths require 1 approval.** CI must be green before merge; there
is no override path for a red build. Pull requests older than **10 days** without
activity are closed automatically.

## 4. Testing

Unit tests run on every push. Integration tests run on merge to `main`. The fleet
simulation suite runs nightly and takes about 40 minutes.

## 5. First Week Checklist

1. Complete security training in Workday (required within **14 days** of start)
2. Get added to your team's PagerDuty schedule (shadow-only for the first 30 days)
3. Ship one small change to production
