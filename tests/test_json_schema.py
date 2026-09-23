"""The committed JSON Schema must stay in step with terms.yaml.

`terms.schema.json` is derived from the LinkML schema and drives editor
validation of definition files. The `.githooks/pre-commit` hook regenerates
it, but a commit can bypass the hook (`--no-verify`, or an unconfigured
`core.hooksPath`), so this is the backstop: if terms.yaml changed and the
JSON Schema was not regenerated, the build's schema and the editor's schema
disagree, and this fails.
"""

from pathlib import Path

from terms_site import json_schema

REPO_ROOT = Path(__file__).resolve().parents[1]
COMMITTED = REPO_ROOT / "terms.schema.json"


def test_committed_json_schema_is_current():
    fresh = json_schema.generate()
    assert COMMITTED.read_text() == fresh, (
        "src/schema/terms.schema.json is stale. Regenerate it with "
        "`uv run python -m terms_site.json_schema`."
    )
