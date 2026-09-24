# Subscription Setup — third-party platform, no custom billing

The product contract is explicit: subscription billing runs on a
third-party email platform at **$29/month** (founding offer: **$87
prepaid for three months**). No custom billing, payment-gateway
integration, or sales-management tooling is built. This document is the
setup checklist; there is intentionally no code here.

## Platform choice

Either platform named in the slice plan works. Recommended default:
**Buttondown** (simpler paid-tier mechanics, clean plaintext email
rendering that matches the canonical text issue, easy PDF attachment /
archive linking). Substack is the acceptable alternative.

## Buttondown configuration checklist

1. Create the newsletter: "The Compliance Chronicle — Texas Cottage Food".
2. Enable **paid subscriptions**: monthly tier at **$29/month**.
3. Create the founding offer: a **$87 charge for a 3-month prepaid
   period** (Buttondown: use a discounted/annual-style custom tier or a
   one-time payment link per the platform's current mechanics; record
   each founding subscriber's paid-through date manually — there are
   twelve of them, a spreadsheet is the system).
4. Set the welcome email to set expectations: monthly issue on the 1st,
   information-not-legal-advice disclaimer verbatim, archive link.
5. Paste the plain-text issue (`issue-NNN.txt`) as the email body; use
   the HTML render (`issue-NNN.html`) only if the platform's editor
   preserves the links. Attach nothing — the PDF archive lives at a
   stable link so every email stays light.
6. Host the PDF archive: upload `archive/` (per-issue PDFs +
   `index.html`) to any static host; link it in the welcome email and
   each issue's footer.
7. Turn off platform features that are out of scope: comments, chat,
   community, referrals widgets (E-004 referral tracking is a
   spreadsheet, not software).

## What "sold by phone" means operationally (E-001)

- The phone call ends with the subscriber paying through the platform's
  own checkout link (sent by text/email while on the call) — the
  operator never handles card numbers.
- Every sale is logged in the call spreadsheet: date, name, email,
  prepaid-through date, consent source (risk R-009 mitigation).

## Hard don'ts

- No custom checkout page. No card data anywhere near the operator.
- No second vertical or bundle tier before 100 subscribers.
- No discounting below the founding offer without recording it as a
  pricing experiment against the B9 hypothesis ($29/month, low
  confidence — the E-001 presell is the test).
