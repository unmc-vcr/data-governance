# UNMC Research Administration Data Governance

**One question, one answer.** This is the shared, authoritative source for what
research administration data at UNMC actually *means* — so two analysts never
answer the same question two different ways.

### → [**Browse the terms**](https://unmc-vcr.github.io/data-governance/)

---

## What this is

Every number in a report rests on a definition — what counts as an *award*,
when a *clinical trial* is considered *active*, how an *effort* percentage is
calculated. When those definitions live in people's heads and scattered
spreadsheets, the same question quietly gets two answers.

Guiding principals for this project include:

- **One definition per term.** Written down, in plain language, with its source of record and calculation rules.
- **One office accountable** for keeping it right — a role, not a person, so it survives staff turnover.
- **A status you can trust.** A term is `draft`, `in review`, `approved`, or `deprecated`, and you always know which.
- **A full history.** Every change is reviewed and recorded. A report written three years ago stays explicable.

The result is a living catalog you can point to in a meeting, cite in a report, and trust across offices.

## Who it's for

- **Analysts and report builders** — look up the approved definition before you build, so your numbers match everyone else's.
- **Data requesters** — understand what you're asking for and who to ask.
- **Source-system owners** — see how your data is defined downstream.
- **Stewards and definition owners** — the people who write, validate, and sign off on terms.

If you build reports, request data, or maintain a system using research
administration data, this applies to you.

## Find your way around the site

| On the site | What you'll find |
| --- | --- |
| [Browse terms](https://unmc-vcr.github.io/data-governance/) | The full catalog of governed terms, by subject area. |
| [How governance works](https://unmc-vcr.github.io/data-governance/how-governance-works.html) | The roles, the term lifecycle, and how a definition becomes official. |
| [How to read a term](https://unmc-vcr.github.io/data-governance/how-to-read-a-term.html) | What every field on a term page means. |
| [Standards](https://unmc-vcr.github.io/data-governance/standards/) | Cross-cutting rules, including data classification. |

## Suggest a change

Definitions improve when the people who use them speak up. Every term page has
a **Suggest a change** link. Proposing an edit opens a request that the
responsible steward reviews — and the approved change becomes part of the
permanent record.

You don't need to be a developer to suggest a change. If you're new to the
mechanics, [How governance works](https://unmc-vcr.github.io/data-governance/how-governance-works.html)
walks through it.

## For developers

We think data governance should follow [FAIR principles](https://www.gofair.foundation/fair-principles).

Here, terms are stored as data, validated against a lightweight schema, and rendered into the site by a
small build pipeline. If you're interested in the technical status of this work, see **[DEVELOPMENT.md](DEVELOPMENT.md)**.