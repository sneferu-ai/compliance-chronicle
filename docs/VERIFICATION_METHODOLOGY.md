# Verification Methodology — The Compliance Chronicle (internal process)

This document is the internal curation process. Its subscriber-visible
output is the **verification ledger** printed in every issue. The gates
in `compliance_chronicle/gates.py` enforce the machine-checkable parts
of this document; the rest is operator discipline.

## 1. The one rule

Every regulatory claim in an issue is either:

- **verified-with-citation** — exact pinpoint citation (instrument +
  section/chapter/bill number) plus a direct link to the authoritative
  source text, or
- **explicitly unverified** — rendered as "we could not verify X" with
  the reason.

There is no third state. Assembly (`compliance_chronicle/assemble.py`)
never drops a claim from the research report; an unverifiable claim is
converted into an unverified item, because silence about a surfaced
claim is a falsification event for the product.

## 2. Authoritative source classes

Encoded as data in `compliance_chronicle/sources.py`. Authority order:

| Rank | Class | Examples |
|---|---|---|
| 100 | `state_statute` | Tex. Health & Safety Code ch. 437 (statutes.capitol.texas.gov) |
| 90  | `state_admin_code` | 25 TAC § 229.661 (Secretary of State TAC viewer) |
| 80  | `fee_schedule` | The publishing body's own posted fee schedule |
| 70  | `state_agency_guidance` | DSHS cottage-food industry page; TDA publications |
| 60  | `county_health` | County/local health authority publications |
| 50  | `legislative_watch` | Filed bills on Texas Legislature Online (watch items, not law) |
| 10  | `secondary_press` | News, Facebook groups, word of mouth — **never sufficient alone** |

A claim cited only to `secondary_press` ships as unverified, with the
lead named. That is a feature: it tells the subscriber what is being
heard without laundering rumor into fact.

## 3. The monthly sweep (required before any "quiet month")

Before an issue may declare *no material changes*, the search log must
contain a dated entry for each of:

1. `state_statute` — ch. 437 re-read.
2. `state_admin_code` — 25 TAC § 229.661 checked for posted changes.
3. `state_agency_guidance` — DSHS cottage-food page re-read.
4. `fee_schedule` — DSHS fee schedules checked.

The gate `quiet-search-log` fails the issue if any class is missing,
if any entry is dated after the publish date, or if the log is empty.
A quiet month without this log **does not ship**.

## 4. Conflict resolution

When two sources disagree, the higher-authority source wins
(`sources.resolve_conflict`). Equal-authority conflicts are not
resolvable by rule: the item ships **unverified** and the reason names
both sources. Guidance never overrides statute or rule; a county
requirement adds to state requirements, never replaces them.

## 5. Operator spot-check (risk R-004 mitigation)

Before an issue ships, the operator clicks every citation link in the
issue and confirms the cited text exists at the link. This is the human
backstop against a fabricated-but-plausible citation from the research
back-end. The `validate` command must pass first; then the operator
spot-checks; then the issue ships.

## 6. Majority-unverifiable issues

If more than half the surfaced items are unverifiable, the issue must
declare the failure (`verification_failure_declared: true`), which
renders a prominent warning banner. Shipping a majority-unverifiable
issue *silently* is a falsification event; the
`verification-majority` gate blocks it.

## 7. What this process never does

- Never offers legal advice or personalized compliance review.
- Never fills in, files, or submits anything on a subscriber's behalf.
- Never upgrades a claim from unverified to verified without a new
  authoritative citation.
