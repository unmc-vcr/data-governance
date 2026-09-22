"""Change history for each term, derived from git.

The design shows a per-term timeline. Rather than ask stewards to hand-maintain
a changelog inside the YAML -- which drifts the moment someone forgets -- the
history is read out of the commits that touched each definition file.

Each file's history is walked separately and attributed only to the terms in
that file. Scoping matters: the same term id can appear in more than one file
over a repository's life (copy a term file, forget to change the id, fix it in
a later commit) and a global id-keyed walk would then splice one file's
commits into another term's timeline.

With the one-term-per-file layout, every commit touching a file belongs to
that file's term, so an identifier rename reads as a rename instead of a
delete plus an unrelated create. Files holding several terms fall back to
matching by id within that file.

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
    if before is None and after is None:
        # The file held no terms at either end of this diff -- it was empty,
        # unparseable, or only carried a subject area. Nothing to report.
        return None
    if before is None:
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
    history: dict[str, list[Change]] = {}

    for path in definition_paths:
        rel_path = str(path.relative_to(repo_root))
        current = _current_term_ids(path)
        if not current:
            continue

        for commit in _file_commits(repo_root, rel_path):
            after = _terms_at(repo_root, commit["sha"], commit["path_after"])
            before = (
                _terms_at(repo_root, commit["parent"], commit["path_before"])
                if commit["parent"] and commit["path_before"]
                else {}
            )

            for term_id, summary in _changes_in_file(before, after, single=len(current) == 1):
                # When the file holds one term, every change to it belongs to
                # that term, even across an identifier rename.
                if len(current) == 1:
                    term_id = current[0]

                detail = summary
                subject = commit["subject"]
                if subject and not subject.lower().startswith(("wip", "fixup!", "merge ")):
                    detail = f"{summary} ({subject})"

                history.setdefault(term_id, []).append(
                    Change(
                        date=commit["date"],
                        iso=commit["iso"],
                        author=commit["author"],
                        summary=detail,
                        commit=commit["sha"][:8],
                    )
                )

    for entries in history.values():
        entries.sort(key=lambda c: c.iso, reverse=True)
    return history


def _current_term_ids(path: Path) -> list[str]:
    """Term ids in the file as it stands now, in file order."""
    try:
        doc = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError):
        return []
    if not isinstance(doc, dict):
        return []
    return [t["id"] for t in doc.get("terms") or [] if isinstance(t, dict) and "id" in t]


def _changes_in_file(before: dict, after: dict, *, single: bool):
    """Yield (term_id, summary) for one commit's effect on one file."""
    if single:
        # One term per file: compare the sole entry on each side, so an
        # identifier rename reads as a rename rather than as a delete and an
        # unrelated create.
        old = next(iter(before.values()), None)
        new = next(iter(after.values()), None)
        summary = _describe(old, new)
        if summary is None:
            return
        if old is not None and new is not None and old.get("id") != new.get("id"):
            summary = f"Identifier changed from {old['id']} to {new['id']}. {summary}"
        # Attributed to the file's current term by the caller.
        yield (new or old)["id"], summary
        return

    for term_id in set(before) | set(after):
        summary = _describe(before.get(term_id), after.get(term_id))
        if summary is not None:
            yield term_id, summary


def _file_commits(repo_root: Path, rel_path: str) -> list[dict]:
    """Commits touching one file, newest first, with its historical paths.

    `--follow` keeps a file's history across renames, which matters because
    renaming a term's file must not reset its timeline. It also means the path
    differs at older commits, so the path to read at each end of the diff is
    taken from the name-status output rather than assumed.
    """
    log = _git(
        repo_root,
        "log",
        "--follow",
        "--name-status",
        "--format=%x00%H%x1f%aI%x1f%an%x1f%s",
        "--",
        rel_path,
    )
    if not log:
        return []

    commits: list[dict] = []
    for chunk in log.split("\x00"):
        if not chunk.strip():
            continue
        lines = [ln for ln in chunk.splitlines() if ln.strip()]
        if not lines:
            continue
        header = lines[0].split("\x1f")
        if len(header) != 4:
            continue
        sha, iso, author, subject = header

        path_after = rel_path
        path_before = rel_path
        is_origin = False
        for status_line in lines[1:]:
            parts = status_line.split("\t")
            code = parts[0]
            if code.startswith("R") and len(parts) >= 3:
                # Rename: the same file under a new name, so its earlier
                # history still belongs to it.
                path_before, path_after = parts[1], parts[2]
            elif code.startswith("C") and len(parts) >= 3:
                # Copy: a NEW file seeded from another that still exists
                # independently. --follow traces into the source's history,
                # but those commits are not this term's, so this is where the
                # timeline starts.
                path_before, path_after = None, parts[2]
                is_origin = True
            elif code.startswith("A") and len(parts) >= 2:
                path_after, path_before = parts[1], None
                is_origin = True
            elif len(parts) >= 2:
                path_after = path_before = parts[1]
            break

        try:
            date = datetime.fromisoformat(iso).strftime("%d %b %Y")
        except ValueError:
            date = iso[:10]

        commits.append(
            {
                "sha": sha,
                "iso": iso,
                "author": author,
                "subject": subject,
                "date": date,
                "path_after": path_after,
                "path_before": path_before,
                "parent": (
                    _git(repo_root, "rev-parse", "--verify", f"{sha}^") or ""
                ).strip(),
            }
        )
        if is_origin:
            # Commits are newest-first, so this file's story starts here.
            break
    return commits


def attach(repo_root: Path, definition_paths: list[Path], glossary) -> None:
    """Attach collected history onto each term in place."""
    collected = collect(repo_root, definition_paths)
    for term in glossary.terms:
        term.history = collected.get(term.id, [])
