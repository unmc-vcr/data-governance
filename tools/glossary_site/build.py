"""Build the site.

    python -m glossary_site.build [--out site] [--skip-reference] [--strict]

The pipeline, in order, with the build stopping at the first failure:

1. Validate every definition file against the schema with `linkml-validate`.
2. Load the data, resolving every cross-reference. Dangling references fail
   here -- `linkml-validate` does not catch them.
3. Apply the governance rules LinkML cannot express (exactly one definition
   owner per term, approved terms cite a source, deprecated terms point to a
   replacement).
4. Read each term's change history out of git.
5. Render the glossary, the authored content, and the gen-doc schema
   reference into one static site.
"""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

from . import checks, content, history, reference, render
from .model import GlossaryError, ROLE_LABELS, load

REPO_ROOT = Path(__file__).resolve().parents[2]

DEFAULT_SCHEMA = REPO_ROOT / "src" / "schema" / "glossary.yaml"
DEFAULT_DEFINITIONS = REPO_ROOT / "src" / "definitions"
DEFAULT_AGENTS = REPO_ROOT / "src" / "agents.yaml"
DEFAULT_CONTENT = REPO_ROOT / "docs" / "content"
DEFAULT_OUT = REPO_ROOT / "site"

REPO_URL = "https://github.com/unmc-vcr/data-governance"

CONTACT_EMAIL = "datagovernance@unmc.edu"
SUGGEST_CHANGE_URL = (
    f"{REPO_URL}/issues/new"
    "?template=term-change.yml&labels=glossary&title=Change+request%3A+&term="
)
# Source links point at the default branch rather than a commit, so they keep
# working as the file changes. A reader following one wants the current file.
REPO_BLOB_URL = f"{REPO_URL}/blob/main/"

RECENT_CHANGE_LIMIT = 6


def _fail(heading: str, problems) -> int:
    sys.stdout.flush()
    print(f"\n{heading}", file=sys.stderr)
    for problem in problems:
        print(f"  - {problem}", file=sys.stderr)
    print("", file=sys.stderr)
    return 1


def build(
    *,
    schema: Path = DEFAULT_SCHEMA,
    definitions_dir: Path = DEFAULT_DEFINITIONS,
    agents: Path = DEFAULT_AGENTS,
    content_dir: Path = DEFAULT_CONTENT,
    out: Path = DEFAULT_OUT,
    skip_reference: bool = False,
    repo_root: Path = REPO_ROOT,
) -> int:
    definition_files = sorted(definitions_dir.glob("*.yaml"))
    if not definition_files:
        return _fail(
            "No definition files found.",
            [f"{definitions_dir} contains no *.yaml files."],
        )

    print(f"Validating {len(definition_files)} definition file(s) against {schema.name}")
    problems = checks.validate_against_schema(
        schema, [*definition_files, agents], repo_root
    )
    if problems:
        return _fail("Schema validation failed:", problems)
    print("  schema validation passed")

    schema_doc = render.load_schema(schema)

    try:
        glossary = load(
            definition_files, agents, repo_root, prefixes=schema_doc.get("prefixes") or {}
        )
    except GlossaryError as exc:
        return _fail("Reference check failed:", [exc])
    print(
        f"  loaded {len(glossary.terms)} term(s) across "
        f"{len(glossary.areas)} subject area(s)"
    )

    problems = checks.check_governance(glossary)
    if problems:
        return _fail("Governance checks failed:", problems)
    print("  governance checks passed")

    for note in checks.warnings(glossary):
        print(f"  warning: {note}")

    history.attach(repo_root, definition_files, glossary)
    with_history = sum(1 for t in glossary.terms if t.history)
    print(f"  change history found for {with_history}/{len(glossary.terms)} term(s)")

    try:
        pages = content.load(content_dir)
    except content.ContentError as exc:
        return _fail("Authored content failed to load:", [exc])
    print(f"  loaded {len(pages)} authored page(s)")

    hub_page = next((p for p in pages if p.is_hub), None)
    if hub_page is None:
        return _fail(
            "No landing page.",
            [
                f"Add a Markdown file under {content_dir} with `hub: true` in its "
                "front matter. That page becomes index.html."
            ],
        )

    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)

    renderer = render.Renderer(
        out,
        glossary,
        nav=[],
        schema=schema_doc,
        contact_email=CONTACT_EMAIL,
        suggest_change_url=SUGGEST_CHANGE_URL,
        repo_blob_url=REPO_BLOB_URL,
    )

    reference_url = None
    if not skip_reference:
        # Nav needs to know whether the reference exists, but the reference
        # renders through the same Renderer, so build nav twice: once without
        # it to render the reference pages, once with it for everything else.
        renderer.nav = render.build_nav(pages, has_reference=True)
        reference_url = reference.build(schema, renderer)
        if reference_url is None:
            print("  gen-doc produced nothing; skipping the schema reference")

    renderer.nav = render.build_nav(pages, has_reference=reference_url is not None)

    renderer.hub(
        hub_page,
        recent_changes=_recent_changes(glossary),
        contacts=_contacts(glossary),
    )
    renderer.glossary_index()
    renderer.search_page()
    renderer.how_to_read(reference_url)

    for area in glossary.areas:
        renderer.area_page(area)
    for term in glossary.terms:
        renderer.term_page(term)
    for page in pages:
        if not page.is_hub:
            renderer.content_page(page)

    renderer.copy_static()
    renderer.write_search_index([p for p in pages if not p.is_hub])

    print(f"\nBuilt {len(renderer.written)} page(s) into {out}")
    return 0


def _recent_changes(glossary):
    """Newest changes across all terms, for the hub timeline."""
    entries = [
        {"term": term, "change": change}
        for term in glossary.terms
        for change in term.history
    ]
    entries.sort(key=lambda e: e["change"].iso, reverse=True)
    return entries[:RECENT_CHANGE_LIMIT]


def _contacts(glossary):
    """Every office holding a role, with the roles it holds."""
    colours = {
        "definition_owner": "var(--navy)",
        "data_steward": "var(--teal)",
        "business_sme": "var(--ink-3)",
    }
    by_agent: dict[str, dict] = {}
    for item in [*glossary.areas, *glossary.terms]:
        for responsibility in item.responsibilities:
            entry = by_agent.setdefault(
                responsibility.agent.id,
                {"agent": responsibility.agent, "roles": set(), "colour": None},
            )
            entry["roles"].add(responsibility.role)

    contacts = []
    for entry in by_agent.values():
        primary = next(
            (r for r in ("definition_owner", "data_steward", "business_sme") if r in entry["roles"]),
            "business_sme",
        )
        contacts.append(
            {
                "agent": entry["agent"],
                "roles": sorted(ROLE_LABELS.get(r, r) for r in entry["roles"]),
                "colour": colours[primary],
            }
        )
    contacts.sort(key=lambda c: c["agent"].pref_label.lower())
    return contacts


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="build-glossary-site",
        description="Build the UNMC data governance static site.",
    )
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT, help="output directory")
    parser.add_argument("--schema", type=Path, default=DEFAULT_SCHEMA)
    parser.add_argument("--definitions", type=Path, default=DEFAULT_DEFINITIONS)
    parser.add_argument("--agents", type=Path, default=DEFAULT_AGENTS)
    parser.add_argument("--content", type=Path, default=DEFAULT_CONTENT)
    parser.add_argument(
        "--skip-reference",
        action="store_true",
        help="skip the gen-doc schema reference (faster local iteration)",
    )
    args = parser.parse_args(argv)

    return build(
        schema=args.schema,
        definitions_dir=args.definitions,
        agents=args.agents,
        content_dir=args.content,
        out=args.out,
        skip_reference=args.skip_reference,
    )


if __name__ == "__main__":
    raise SystemExit(main())
