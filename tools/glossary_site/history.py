"""Change history for each term, derived from git.

The design shows a per-term timeline. Rather than ask stewards to hand-maintain
a changelog inside the YAML -- which drifts the moment someone forgets -- the
history is read out of the commits that touched each definition file.

For every commit touching a definition file, the file is parsed at that commit
and at its parent, and the two term maps are diffed. That gives a per-term
history from a per-file log.

This degrades to an empty history rather than failing: a shallow clone, a
missing git binary, or a fresh worktree should not break the build. CI uses
`fetch-depth: 0` so the real history is present there.
"""

from __future__ import annotations

import subprocess
from datetime import datetime
from pathlib import Path

import yaml

from .model import Change, STATUS_LABELS

# A commit touching more definition files than this is almost certainly a bulk
# reformat; parsing every version of every file gets slow and the resulting
# "changed" entries are noise.
MAX_FILES_PER_COMMIT = 25


def _git(repo_root: Path, *args: str) -> str | None:
    try:
        result = subprocess.run(
            ["git", *args],
            cwd=repo_root,
            capture_output=True,
            text=True,
            check=False,
        )
    except (OSError, FileNotFoundError):
        return None
    if result.returncode != 0:
        return None
    return result.stdout


def _terms_at(repo_root: Path, rev: str, rel_path: str) -> dict[str, dict]:
    """Term id -> term body, as of `rev`. Empty if the file did not exist."""
    blob = _git(repo_root, "show", f"{rev}:{rel_path}")
    if blob is None:
        return {}
    try:
        doc = yaml.safe_load(blob) or {}
    except yaml.YAMLError:
        return {}
    if not isinstance(doc, dict):
        return {}
    return {t["id"]: t for t in doc.get("terms") or [] if isinstance(t, dict) and "id" in t}


def _describe(before: dict | None, after: dict | None) -> str | None:
    """Plain-language summary of what changed about one term."""
    if before is None and after is not None:
        return "Term created."
    if after is None:
        return "Term removed from the glossary."
    if before == after:
        return None

    notes: list[str] = []
    if before.get("status") != after.get("status"):
        old = STATUS_LABELS.get(before.get("status"), before.get("status"))
        new = STATUS_LABELS.get(after.get("status"), after.get("status"))
        notes.append(f"Status changed from {old} to {new}.")
    if (before.get("definition") or "").strip() != (after.get("definition") or "").strip():
        notes.append("Definition reworded.")
    if before.get("responsibilities") != after.get("responsibilities"):
        notes.append("Responsibility reassigned.")
    if before.get("source_of_record") != after.get("source_of_record"):
        notes.append("Source of record changed.")
    if before.get("classification") != after.get("classification"):
        notes.append("Classification changed.")
    if before.get("rules") != after.get("rules"):
        notes.append("Rules and qualifiers updated.")
    if before.get("replaced_by") != after.get("replaced_by"):
        notes.append("Replacement term set.")

    if not notes:
        notes.append("Details updated.")
    return " ".join(notes)


def collect(repo_root: Path, definition_paths: list[Path]) -> dict[str, list[Change]]:
    """Map term id -> newest-first list of changes."""
    rel_paths = [str(p.relative_to(repo_root)) for p in definition_paths]
    if not rel_paths:
        return {}

    log = _git(
        repo_root,
        "log",
        "--format=%H%x1f%aI%x1f%an%x1f%s",
        "--",
        *rel_paths,
    )
    if not log:
        return {}

    history: dict[str, list[Change]] = {}

    for line in log.splitlines():
        if not line.strip():
            continue
        parts = line.split("\x1f")
        if len(parts) != 4:
            continue
        sha, iso, author, subject = parts

        changed = _git(
            repo_root,
            "diff-tree",
            "--no-commit-id",
            "--name-only",
            "-r",
            # Without --root, diff-tree lists nothing for the repository's
            # first commit, which would silently drop the "Term created"
            # entry for every term introduced in it.
            "--root",
            sha,
            "--",
            *rel_paths,
        )
        touched = [p for p in (changed or "").splitlines() if p.strip()]
        if not touched or len(touched) > MAX_FILES_PER_COMMIT:
            continue

        parent = (_git(repo_root, "rev-parse", "--verify", f"{sha}^") or "").strip()

        try:
            date = datetime.fromisoformat(iso).strftime("%d %b %Y")
        except ValueError:
            date = iso[:10]

        for rel_path in touched:
            after = _terms_at(repo_root, sha, rel_path)
            before = _terms_at(repo_root, parent, rel_path) if parent else {}

            for term_id in set(before) | set(after):
                summary = _describe(before.get(term_id), after.get(term_id))
                if summary is None:
                    continue
                # Prefer the commit subject when the author wrote a real one;
                # fall back to the derived summary.
                detail = summary
                if subject and not subject.lower().startswith(("wip", "fixup!", "merge ")):
                    detail = f"{summary} ({subject})"
                history.setdefault(term_id, []).append(
                    Change(
                        date=date,
                        iso=iso,
                        author=author,
                        summary=detail,
                        commit=sha[:8],
                    )
                )

    for entries in history.values():
        entries.sort(key=lambda c: c.iso, reverse=True)
    return history


def attach(repo_root: Path, definition_paths: list[Path], glossary) -> None:
    """Attach collected history onto each term in place."""
    collected = collect(repo_root, definition_paths)
    for term in glossary.terms:
        term.history = collected.get(term.id, [])
