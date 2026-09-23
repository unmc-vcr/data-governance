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
we make that true: one definition per term, one office accountable for it, and a
written trail of every change.

If you build reports, request data, or maintain a source system, this applies to
you.

## Who does what

Every term names exactly one **definition owner**. The other two roles are
optional but strongly encouraged — a definition nobody has checked against real
data is a guess.

### Definition owner

Writes and maintains the wording of a term, including its source of record and
its calculation rules. Accountable for approving the definition. Exactly one per
term, enforced by the build.

### Data steward

Responsible for the quality of the data implementing the term. Approves access,
and answers when the number looks wrong.

### Business SME

Knows how the data is produced in practice. Consulted before any definition
changes; not accountable for approval.

> **Good to know**
> Responsibility sits with an office, never with a named individual. An office
> IRI survives staff turnover; a person's name does not. If you need to know who
> to ask for by name, the office lists the people who currently staff it — a
> directory only. A person can staff more than one office, and moving between
> offices changes nothing about what an office is accountable for.

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

> **Good to know**
> `definition_source` records where wording was *adopted from* — an NIH policy
> page, Uniform Guidance, a professional standard. Most local definitions are
> written here and correctly have none. Its absence is not a gap; the merged
> pull request is what records the approval.