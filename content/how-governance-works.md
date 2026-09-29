---
title: How research administration data governance works
eyebrow: Start here
lede: >-
  A term becomes official when a definition owner writes it, a steward validates
  it against real data, and the changed is approved by the council.
nav_group: Start here
nav_label: How governance works
order: 10
meta:
  #- "Maintained by: Research Administration Data Governance Program"
toc: true
---

## Purpose

Two analysts should never answer the same question two ways. Governance is how
we make that true: one definition per term, one office accountable for the term, a verified
steward, relevant subject matter experts, and a written trail of every change.

If you build reports, request data, or maintain a source system using Research Administration
data, data governance applies to you.


### Definition owner

Writes and maintains the wording of a term, including its source of record and
its calculation rules. Accountable for approving the definition.

### Data steward

Responsible for the quality of the data implementing the term. Approves access, answers questions
from the data community, and responds to data quality issues.

### Business SME

Knows how the data is produced in practice. Consulted before any definition
changes; not accountable for approval.

## The lifecycle of a term

A term's state is not a field someone sets. It follows from the dated steps
recorded on the term: drafted, submitted for review, approved.

| State | What it means | Can you build on it? |
| --- | --- | --- |
| Proposed | Drafted, or submitted for review; the steward and SME may still be validating it against real data. | Reference only |
| Approved | Signed off. The definition is stable. | Yes |
| Deprecated | Superseded, with a pointer to its replacement. | Historical reconciliation only |

Each term page lists those steps, with their dates, under *History*.
Deprecated terms stay visible with a link to what replaced them. We never delete
history — a report written three years ago has to remain explicable.

## Requesting a change

Use the *Suggest a change* link on the term page, or edit the term's YAML 
source file directly and open a pull request.