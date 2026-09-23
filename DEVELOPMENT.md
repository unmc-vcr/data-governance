# Developer guide

Technical reference for the UNMC Research Administration Data Governance
repository — the schema, the build pipeline, and the static site that publishes
the governed terms. If you're here to *read* or *suggest a change to* a term,
you want the [published site](https://unmc-vcr.github.io/data-governance/), not
this file; see the [README](README.md).

## The core idea: terms are data, not schema

A small LinkML schema (`src/schema/terms.yaml`) describes the *shape* of a term;
the terms themselves are YAML data files in `src/definitions/`, validated
against it. Rewording a definition is a data change, not a schema release, and
local UNMC concepts never leak into the community LinkML Research Administration
model.

## Quick start

```bash
uv sync --group dev
```

Enable the git hooks (once per clone) so `terms.schema.json` stays in step
with the schema — see [Editor validation](#editor-validation):

```bash
git config core.hooksPath .githooks
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
| `terms.schema.json` | JSON Schema derived from `terms.yaml`, for editor validation. Generated artifact — see [Editor validation](#editor-validation). |
| `.githooks/` | Git hooks. `pre-commit` regenerates `terms.schema.json` when `terms.yaml` changes. |
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

## Editor validation

The build's stage 1 validates definition files with `linkml-validate`, but
that only runs when you run the build. To catch a malformed term *as you
type*, the repository ships a JSON Schema derived from `terms.yaml`, and
`.vscode/` points the YAML language server at it.

Install the [Red Hat YAML extension](https://marketplace.visualstudio.com/items?itemName=redhat.vscode-yaml)
(`redhat.vscode-yaml`) — VS Code offers it automatically from
`.vscode/extensions.json`. With it installed, `.vscode/settings.json` maps
`src/definitions/**/*.yaml` and `src/agents.yaml` to `terms.schema.json`, so
a wrong status value, a missing required slot, or an unknown key is
underlined in the editor, with hover docs pulled from the schema
descriptions.

`terms.schema.json` at the repository root is a generated artifact, derived
from `terms.yaml` — do not edit it by hand. It is committed (unlike the
`site/` build output) because the editor and a fresh clone both need it
present.

A pre-commit hook keeps it from drifting: when a commit touches `terms.yaml`,
the hook regenerates `terms.schema.json` and stages it into the same commit.
Enable the hook once per clone:

```bash
git config core.hooksPath .githooks
```

To regenerate by hand — for instance after editing `terms.yaml` without
committing yet:

```bash
uv run python -m terms_site.json_schema
```

`tests/test_json_schema.py` is the backstop: it fails if the committed copy
has drifted, so CI catches a stale schema even when the hook is bypassed
(`git commit --no-verify`, or a clone that never set `core.hooksPath`).

Two schemas, one source of truth: the editor validates against the JSON
Schema, the build validates against `terms.yaml` itself, and the drift test
keeps them from disagreeing. The JSON Schema checks *shape* only — the same
things `linkml-validate` checks. Cross-references and the governance rules
(stages 2–3) are still only enforced by the build.

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

`.github/workflows/site.yml` publishes to **GitHub Pages**.

- **Every pull request** — run tests, validate, build, check internal links,
  and upload the site as the `terms-site` artifact. Download it, unzip, open
  `index.html`: the site uses relative links throughout, so it needs no server.
  Nothing deploys.
- **Push to `main`** — the same, then deploy to Pages.

The checkout uses `fetch-depth: 0` because each term's change history is read
from the commits touching its own file. With a shallow clone every timeline
renders empty, silently.

### Setup

1. Settings → Pages → Source: **GitHub Actions**.
2. Pages requires the repository to be public, or GitHub Team / Enterprise
   Cloud on a private one.
3. If the site is served from a project subpath
   (`https://<org>.github.io/<repo>/`) rather than a custom domain, pass that
   prefix to the build so the 404 page resolves its assets:

   ```bash
   uv run python -m terms_site.build --base-path /<repo>/
   ```

   Every other page computes its own relative prefix and works at any depth;
   only `404.html` needs this, because it is served in response to arbitrary
   URLs. A custom domain avoids the flag entirely — and avoids baking the repo
   name into every w3id redirect target.

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
- **The published site is anonymous.** Pages serves it to anyone with the
  link, so everything in `src/definitions/` is public once the repository is.
  Sensitive subject areas belong in a separate private repository — see
  `docs/plans/` for that design.
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
