"""Emit a JSON Schema so an editor can validate definition files as you type.

`linkml-validate` (build stage 1) is the authority on whether a definition
file is well shaped, but it only runs when you run the build. Editors don't
speak LinkML; they speak JSON Schema. So this derives one from `terms.yaml`
and writes it to `terms.schema.json` at the repository root -- a generated
artifact, kept out of `src/` -- and `.vscode/` points the YAML language
server at it for the `src/definitions/**` and `src/agents.yaml` files.

The top class is `Terms`, the per-file container, so the generated schema
matches whole definition files -- the same `subject_areas` / `terms` /
`agents` / `people` shape every file under `src/definitions/` uses.

The `.githooks/pre-commit` hook regenerates and stages this file whenever
`terms.yaml` is part of a commit, so the committed copy never drifts. To
regenerate by hand:

    uv run python -m terms_site.json_schema

`tests/test_json_schema.py` fails if the committed file has drifted from the
schema, so CI catches a stale copy even when the hook is bypassed.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SCHEMA = REPO_ROOT / "src" / "schema" / "terms.yaml"
# A generated artifact, deliberately at the repository root rather than under
# src/ -- it is derived from the schema, not authored.
DEFAULT_OUT = REPO_ROOT / "terms.schema.json"

# The per-file container: its slots (subject_areas, terms, agents, people)
# become the top-level keys the editor validates.
TOP_CLASS = "Terms"


def generate(schema: Path = DEFAULT_SCHEMA) -> str:
    """Return the JSON Schema for a definition file as a string."""
    result = subprocess.run(
        ["gen-json-schema", "--top-class", TOP_CLASS, str(schema)],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(f"gen-json-schema failed:\n{result.stderr}")
    # gen-json-schema pretty-prints with a trailing newline of its own.
    return result.stdout if result.stdout.endswith("\n") else result.stdout + "\n"


def write(schema: Path = DEFAULT_SCHEMA, out: Path = DEFAULT_OUT) -> Path:
    """Generate the JSON Schema and write it to `out`. Returns the path."""
    out.write_text(generate(schema))
    return out


def main() -> int:
    out = write()
    print(f"Wrote {out.relative_to(REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
