---
title: Data classification standard
eyebrow: Standard · DG-014
badge: Draft
lede: >-
  Every dataset carries one of four tiers. The tier decides where it can live,
  who can see it, and how long you keep it.
nav_group: Standards
nav_label: Data classification
order: 10
meta:
  - "Status: PROVISIONAL — not yet approved"
  - "Owner: Compliance & Privacy (proposed)"
toc: true
---

> **Required**
> This page is a **draft**. The four tiers below were carried over from the site
> design and have not been reviewed or approved by Compliance & Privacy. Do not
> cite this page as policy, and do not use it to justify a handling decision.
> Confirm the real scheme with Compliance & Privacy, then replace this page and
> the `DataClassification` enum in `src/schema/glossary.yaml` together.

## The four tiers

### Public

*No approval needed.* Cleared for open release. Anyone inside or outside the
university may see it.

Examples: published abstracts, aggregate enrollment counts, policy documents.

### Internal

*UNMC login required.* Routine operating data. Share freely inside the
university; do not post publicly.

Examples: award numbers, protocol numbers, department rosters.

### Sensitive

*Steward approval required.* Disclosure would cause real harm to a person or to
the institution. Access is granted per project, with an end date.

Examples: adverse events, consent records, unpublished results.

### Restricted

*Enclave only, IRB tied.* Regulated identifiable data. Never leaves an approved
environment.

Examples: PHI with identifiers, genomic sequence, legacy subject identifiers.

## Handling requirements

| Control | Public | Internal | Sensitive | Restricted |
| --- | --- | --- | --- | --- |
| Storage | Anywhere | University systems | Approved systems | Enclave only |
| Sharing outside UNMC | Permitted | With agreement | DUA required | IRB + DUA |
| Email | Permitted | Permitted | Encrypted | Prohibited |
| Local copies | Permitted | Discouraged | Prohibited | Prohibited |
| Retention | Indefinite | 7 years | Per protocol | Per protocol |

> **In review**
> The retention figures above are placeholders. Retention is set by records
> schedule and by protocol, not by classification tier, and the two have to be
> reconciled before this page can be approved.

## How a tier gets assigned

A term's tier is recorded in its YAML, in the `classification` slot, and appears
on the term page in the *Handling at a glance* panel. Changing a tier is a
governance change like any other: open a pull request, and the steward office for
that subject area reviews it.

## Exceptions

Exceptions are granted for a named project, with an end date, by the
subject-area steward together with Compliance & Privacy. Every exception is
recorded here and re-reviewed at expiry.

Once this standard is approved, this section needs a real request route —
currently there is none.
