# Publishing Schedule — The Compliance Chronicle

## The published cadence

- **Research sweep:** the monthly Sneferu Research run is staged on the
  **25th of each month** (or the next business day), covering the
  current calendar month.
- **Curation and gates:** 25th–end of month. `validate` must pass and
  the operator spot-check (methodology §5) must be done.
- **Publication:** the **1st of the following month**, covering the
  month just ended. Issue #N covering 2026-08 publishes 2026-09-01.

## Lead-time guarantee

An issue that reports a deadline must arrive **before** that deadline.
The `lead-time` gate hard-fails any issue whose publish date is on or
after the earliest deadline it reports, and warns when the lead is
under 7 days.

The structural protection is the **forward deadline calendar**: any
deadline that falls inside the minimum lead window for next month's
issue must appear in *this* month's calendar, so the subscriber always
sees a deadline at least one full issue cycle before it bites. A
deadline discovered too late for that is exactly the case the warning
exists to surface — the fix is to publish a corrected calendar entry
promptly, not to wait for the next monthly issue.

## Quiet months

A quiet month still publishes on schedule, as a "no material changes"
confirmation with the auditable search log and the forward deadline
calendar. Skipping an issue because nothing changed is a falsification
event.

## Missed-issue contingency

If the research back-end is unavailable for a cycle (risk R-008), the
operator produces the issue from the manual fallback checklist — the
same sweep in methodology §3, done by hand against the same sources —
and the issue says so. The schedule slips for no one: a manual, honest
issue beats an automated silence.
