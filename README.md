# UNMC Research Administration Data Governance

Governed business terms for research data at UNMC, and the static site that
publishes them.

The core idea: **terms are data, not schema.** A small LinkML schema
(`src/schema/terms.yaml`) describes the *shape* of a term; the terms
themselves are YAML data files in `src/definitions/`, validated against it.
Rewording a definition is a data change, not a schema release, and local
UNMC concepts never leak into the community LinkML Research Administration
model.

## Quick start

```bash
uv sync --group dev
```

```bash
uv run python -m terms_site.build
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
| `src/schema/terms.yaml` | The LinkML schema. Defines `Term`, `SubjectArea`, and the enums. |
| `src/definitions/<area>/<area>.yaml` | A subject area declaration. |
| `src/definitions/<area>/terms/*.yaml` | The governed terms, **one file per term**. |
| `src/agents.yaml` | Registry of offices that can hold a governance role. |
| `docs/content/**.md` | Authored narrative: the hub, the governance guide, standards. |
| `tools/terms_site/` | The site generator. |
| `tests/` | Test suite, with its own fixture term set. |

## How the build works

`python -m terms_site.build` runs five stages and stops at the first
failure:

1. **Validate** every definition file against the schema with
   `linkml-validate`.
2. **Load and resolve** every cross-reference. `linkml-validate` checks shapes,
   not the graph — a `broader:` pointing at a term that does not exist passes
   validation and fails here.
3. **Apply governance rules** LinkML cannot express: exactly one
   `definition_owner` per term, identifiers that expand to usable IRIs,
   deprecated terms point at a replacement, no cycles in `broader`.
4. **Read change history** from `git log` over the definition files, diffing
   each commit against its parent to attribute changes to individual terms.
5. **Render** the terms, the authored Markdown, and the `gen-doc` schema
   reference into one static site.

Useful flags:

```bash
uv run python -m terms_site.build --skip-reference
```

That skips the `gen-doc` pass, which is most of the build time, for faster
local iteration on templates.

### Why not `gen-doc` alone?

`gen-doc` documents the **schema**, not the terms. Run it on `terms.yaml`
and you get pages for `Term`, `SubjectArea`, every slot, and every enum —
and the words "Clinical Trial" appear nowhere in the output. Stakeholders
care about the terms. So the site has two halves:

- **Term pages**, rendered from `src/definitions/` — the primary audience.
- **Schema reference**, from `gen-doc`, wrapped in the same page shell so it
  does not look like a different website — the technical audience.

`gen-doc -f html` is deliberately unused: it requires a full custom template
for every element type, which is more work than rendering the Markdown
ourselves.

### Why one file per term

Term change history is derived from the commits that touch a term's file. If
several terms shared a file, editing one would appear in every other term's
timeline, and `git log` could not tell them apart. One file per term keeps the
history — and the *View source on GitHub* link — precise. Definition files are
discovered recursively, so adding a subject area is just adding a directory.

## Adding or changing a term

1. Edit the term's file under `src/definitions/<area>/terms/`, or add a new
   one. To add a subject area, create `src/definitions/<area>/<area>.yaml`
   with a `subject_areas:` block and a `terms/` directory beside it.
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

`definition_source` is optional at every status. It records where wording was
*adopted from*, so a definition authored at UNMC correctly has none.

### Governance roles

Responsibility attaches to an **office**, never a named individual — an office
IRI survives staff turnover. Every agent referenced from a term must be
registered in `src/agents.yaml`, and each term needs exactly one
`definition_owner`.

The shape is a `responsibilities` list of PROV `Attribution` value objects
(`prov:qualifiedAttribution` / `prov:agent` / `prov:hadRole`), chosen over
three flat slots so a fourth role can be added without a schema change.

## CI/CD

`.github/workflows/site.yml` deploys to **Azure Static Web Apps**. GitHub Pages
is not used: this repository is private, and Pages on a private repository
requires GitHub Team or Enterprise Cloud.

- **Every pull request** — run tests, validate, build, check internal links,
  then deploy to a per-PR staging site. The preview URL is posted as a comment
  on the PR and updated in place on each push. Closing the PR tears the staging
  site down. The build is also uploaded as the `terms-site` artifact, so a
  reviewer can open `index.html` from the zip without signing in.
- **Push to `main`** — the same, then deploy to the production site.

The checkout uses `fetch-depth: 0` because each term's change history is read
from the commits touching its own file. With a shallow clone every timeline
renders empty.

### One-time setup

1. Create the Static Web App in Azure (the Free plan is enough for a static
   site of this size).
2. Confirm the repository secret
   `AZURE_STATIC_WEB_APPS_API_TOKEN_POLITE_GLACIER_0E6778E10` exists. Azure
   creates it automatically when the Static Web App is linked to the
   repository, naming it after the resource. If the resource is ever recreated
   the name changes, and both `azure_static_web_apps_api_token` lines in the
   workflow have to be updated to match.
3. Configure the Azure AD identity provider, because `staticwebapp.config.json`
   requires authentication (see below).

### Access control

`staticwebapp.config.json` is deliberately **closed by default**: every route
requires an authenticated user, and a 401 redirects to `/.auth/login/aad`. This
repository is private and the term set carries internal operational
definitions, so publishing it anonymously should be a deliberate act, not a
default.

To open the site to anyone with the link, change the `/*` route's
`allowedRoles` to `["anonymous"]`. To restrict further, assign a custom role in
Azure and require that instead of `authenticated` — otherwise any account in
the configured directory can read the site.

The file is tracked at the repository root and copied into `site/` during the
build, because it has to sit at the root of the deployed content and `site/` is
gitignored.

## Known gaps

These are real and deliberate, not oversights:

- **The namespace is not registered yet.** `https://w3id.org/unmc/terms/` is not
  registered. Term IRIs do not resolve. Register a real w3id namespace and
  replace the `unmc:` prefix in `src/schema/terms.yaml`.
- **Data classification is provisional.** The four tiers (Public / Internal /
  Sensitive / Restricted) and the handling matrix were carried over from the
  site design and have **not** been approved by Compliance & Privacy. The
  schema, the standard page, and the term sidebar all say so. Confirm the real
  scheme, then update the `DataClassification` enum and
  `docs/content/standards/data-classification.md` together.
- **`CODEOWNERS` uses placeholder team handles.** GitHub does not warn about an
  unknown owner — the rule is silently ineffective. Create the teams and verify
  with a test PR.
- **The Azure Static Web App has to exist before the first deploy.** Until
  `AZURE_STATIC_WEB_APPS_API_TOKEN` is set, the deploy step fails while every
  step before it — tests, validation, build, link check — still runs, and the
  `terms-site` artifact is still produced.
- **Anyone in the Azure AD tenant can read the site** once authenticated. The
  config requires sign-in, not membership of a particular group. Narrow it with
  a custom role if the term set should be restricted further.
- **Fonts load from Google Fonts.** On a network that blocks them the site
  falls back to system fonts and still reads fine, but the typography is not
  the designed one. Self-host the three families if that matters.
- **`unmc:ClinicalStudy` has a TODO definition.** It is `draft`, so the build
  allows it; it cannot be promoted to `approved` until it is written.

## Tooling notes

Verified against linkml 1.11.1:

- `linkml-validate -s <schema> -C Terms <files>` works and exits non-zero on
  failure.
- **Do not use `linkml-validate --config`.** It reported "No issues found" on a
  file with a known-invalid status value, and it does not expand globs.
- `linkml-validate` does not check references. That is what stage 2 of the
  build is for.

## Tests

```bash
uv run pytest
```

The suite runs against its own fixture term set in `tests/fixtures/`, not
against the real definitions, so adding a term never breaks a test.
