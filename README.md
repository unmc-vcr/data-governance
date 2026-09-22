# UNMC Research Data Governance

Governed business terms for research data at UNMC, and the static site that
publishes them.

The core idea: **terms are data, not schema.** A small LinkML schema
(`src/schema/glossary.yaml`) describes the *shape* of a term; the terms
themselves are YAML data files in `src/definitions/`, validated against it.
Rewording a definition is a data change, not a schema release, and local
UNMC concepts never leak into the community LinkML Research Administration
model.

## Quick start

```bash
uv sync --group dev
```

```bash
uv run python -m glossary_site.build
```

The site lands in `site/`. Open `site/index.html` directly — it uses relative
links throughout and needs no web server.

To preview with a server instead:

```bash
python3 -m http.server 8765 --directory site
```

## Repository layout

| Path | What it is |
| --- | --- |
| `src/schema/glossary.yaml` | The LinkML schema. Defines `Term`, `SubjectArea`, and the enums. |
| `src/definitions/*.yaml` | The governed terms, one file per subject area. |
| `src/agents.yaml` | Registry of offices that can hold a governance role. |
| `docs/content/**.md` | Authored narrative: the hub, the governance guide, standards. |
| `tools/glossary_site/` | The site generator. |
| `tests/` | Test suite, with its own fixture glossary. |

## How the build works

`python -m glossary_site.build` runs five stages and stops at the first
failure:

1. **Validate** every definition file against the schema with
   `linkml-validate`.
2. **Load and resolve** every cross-reference. `linkml-validate` checks shapes,
   not the graph — a `broader:` pointing at a term that does not exist passes
   validation and fails here.
3. **Apply governance rules** LinkML cannot express: exactly one
   `definition_owner` per term, approved terms cite a `definition_source`,
   deprecated terms point at a replacement, no cycles in `broader`.
4. **Read change history** from `git log` over the definition files, diffing
   each commit against its parent to attribute changes to individual terms.
5. **Render** the glossary, the authored Markdown, and the `gen-doc` schema
   reference into one static site.

Useful flags:

```bash
uv run python -m glossary_site.build --skip-reference
```

That skips the `gen-doc` pass, which is most of the build time, for faster
local iteration on templates.

### Why not `gen-doc` alone?

`gen-doc` documents the **schema**, not the terms. Run it on `glossary.yaml`
and you get pages for `Term`, `SubjectArea`, every slot, and every enum —
and the words "Clinical Trial" appear nowhere in the output. Stakeholders
care about the terms. So the site has two halves:

- **Glossary pages**, rendered from `src/definitions/` — the primary audience.
- **Schema reference**, from `gen-doc`, wrapped in the same page shell so it
  does not look like a different website — the technical audience.

`gen-doc -f html` is deliberately unused: it requires a full custom template
for every element type, which is more work than rendering the Markdown
ourselves.

## Adding or changing a term

1. Edit the subject area's file in `src/definitions/`.
2. Run the build locally. Fix whatever it complains about.
3. Open a pull request. CI validates and publishes a preview artifact.
4. The steward office reviews the **rendered pages**, not the YAML diff.
5. Merge. The merged pull request is the approval record.

`.github/CODEOWNERS` routes each subject-area file to its steward office, so
the right reviewers are requested automatically.

### Term status

| Status | Meaning | Citable in reporting? |
| --- | --- | --- |
| `draft` | Written, unchecked. | No |
| `in_review` | Steward and SME validating it. | Reference only |
| `approved` | Signed off. | Yes |
| `deprecated` | Superseded; `replaced_by` points at the successor. | Historical only |

An `approved` term without a `definition_source` fails the build.

### Governance roles

Responsibility attaches to an **office**, never a named individual — an office
IRI survives staff turnover. Every agent referenced from a term must be
registered in `src/agents.yaml`, and each term needs exactly one
`definition_owner`.

The shape is a `responsibilities` list of PROV `Attribution` value objects
(`prov:qualifiedAttribution` / `prov:agent` / `prov:hadRole`), chosen over
three flat slots so a fourth role can be added without a schema change.

## CI/CD

`.github/workflows/site.yml`:

- **Every pull request** — run tests, validate, build, check internal links,
  upload the site as the `glossary-site` artifact. Download it and open
  `index.html` to review; it works straight out of the zip.
- **Push to `main`** — the same, then deploy to GitHub Pages.

The checkout uses `fetch-depth: 0` because term change history is read from
git. With a shallow clone the history panels render empty rather than failing.

## Known gaps

These are real and deliberate, not oversights:

- **The namespace is a placeholder.** `https://w3id.org/unmc/glossary/` is not
  registered. Term IRIs do not resolve. Register a real w3id namespace and
  replace the `unmc:` prefix in `src/schema/glossary.yaml`.
- **Data classification is provisional.** The four tiers (Public / Internal /
  Sensitive / Restricted) and the handling matrix were carried over from the
  site design and have **not** been approved by Compliance & Privacy. The
  schema, the standard page, and the term sidebar all say so. Confirm the real
  scheme, then update the `DataClassification` enum and
  `docs/content/standards/data-classification.md` together.
- **`CODEOWNERS` uses placeholder team handles.** GitHub does not warn about an
  unknown owner — the rule is silently ineffective. Create the teams and verify
  with a test PR.
- **GitHub Pages on a private repository** requires GitHub Team or Enterprise
  Cloud. If the deploy job fails, either enable Pages under
  Settings → Pages → Source: GitHub Actions, or delete the `deploy` job and
  publish the artifact another way. Everything up to deployment still works.
- **Fonts load from Google Fonts.** On a network that blocks them the site
  falls back to system fonts and still reads fine, but the typography is not
  the designed one. Self-host the three families if that matters.
- **`unmc:ClinicalStudy` has a TODO definition.** It is `draft`, so the build
  allows it; it cannot be promoted to `approved` until it is written.

## Tooling notes

Verified against linkml 1.11.1:

- `linkml-validate -s <schema> -C Glossary <files>` works and exits non-zero on
  failure.
- **Do not use `linkml-validate --config`.** It reported "No issues found" on a
  file with a known-invalid status value, and it does not expand globs.
- `linkml-validate` does not check references. That is what stage 2 of the
  build is for.

## Tests

```bash
uv run pytest
```

The suite runs against its own fixture glossary in `tests/fixtures/`, not
against the real definitions, so adding a term never breaks a test.
