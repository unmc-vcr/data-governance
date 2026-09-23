---
title: How research administration data governance works
eyebrow: Start here
lede: >-
  A term becomes official when a definition owner writes it, a steward validates
  it against real data, and the change is merged.
nav_group: Start here
nav_label: How governance works
order: 10
meta:
  - "Maintained by: Research Administration Data Governance Program"
toc: true
---

## Purpose

Two analysts should never answer the same question two ways. Governance is how
we make that true: one definition per term, one office accountable for the term, a verified
steward, relevant subject matter experts, and a written trail of every change.

If you build reports, request data, or maintain a source system using Research Administration
data, data governance applies to you.

## Who does what

Every term names exactly one **definition owner**. The other two roles are
optional but strongly encouraged — a definition nobody has checked against real
data is a guess.

### Definition owner

Writes and maintains the wording of a term, including its source of record and
its calculation rules. Accountable for approving the definition.

### Data steward

Responsible for the quality of the data implementing the term. Approves access,
and answers when the number looks wrong.

### Business SME

Knows how the data is produced in practice. Consulted before any definition
changes; not accountable for approval.

## The lifecycle of a term

| Status | What it means | Can you build on it? |
| --- | --- | --- |
| Draft | The owner has written a definition but nobody has checked it. | No |
| In Review | The steward and SME are validating it against real data. | Reference only |
| Approved | Signed off. The definition is stable. | Yes |
| Deprecated | Superseded, with a pointer to its replacement. | Historical reconciliation only |

Deprecated terms stay visible with a link to what replaced them. We never delete
history — a report written three years ago has to remain explicable.

## Requesting a change

Changes are pull requests against this repository. That is the whole mechanism,
and it is deliberate: the merged pull request *is* the approval record, with the
reviewer, the timestamp, and the diff all attached to it.

1. **Open a request.** Use the *Suggest a change* link on the term page, or edit
   the subject area's YAML file directly and open a pull request.
2. **The build checks it.** Validation runs on every pull request: the schema is
   enforced, references are resolved, and the governance rules are applied.
3. **The steward reviews the rendered page, not the diff.** Every pull request
   publishes a preview of the site as a downloadable artifact. Reviewers read the
   term the way a reader will see it.
4. **Merge is approval.** `CODEOWNERS` routes each subject-area file to its
   steward office, so the right people are required reviewers automatically.