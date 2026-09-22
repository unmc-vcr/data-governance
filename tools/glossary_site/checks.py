"""Validation gate. Nothing renders until this passes.

Two layers, because they catch different things:

1. `linkml-validate` checks each file against the schema -- required slots,
   enum membership, patterns, ranges. It does NOT check that references
   resolve, and it does not know that a term needs exactly one definition
   owner.
2. The checks below cover what LinkML cannot express. Dangling references are
   caught in model.load(); the rest are here.

Do not switch linkml-validate to `--config` mode. It reported "No issues
found" on a file with a known-invalid status value, and it does not expand
globs.
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path

import re

from .model import Glossary, ROLE_LABELS

# `uriorcurie` is checked loosely, so `unmc:Research Project` validates
# cleanly and then expands to an IRI containing a space, which is invalid and
# will not resolve. Identifiers are checked here instead.
VALID_ID = re.compile(r"^[A-Za-z][A-Za-z0-9._-]*:[A-Za-z0-9._~/\-]+$")


@dataclass
class Problem:
    where: str
    message: str

    def __str__(self) -> str:
        return f"{self.where}: {self.message}"


def validate_against_schema(
    schema: Path, data_files: list[Path], repo_root: Path
) -> list[Problem]:
    """Run linkml-validate and turn a non-zero exit into problems."""
    if not data_files:
        return [Problem(str(repo_root), "no definition files found")]

    result = subprocess.run(
        [
            "linkml-validate",
            "-s",
            str(schema),
            "-C",
            "Glossary",
            *[str(p) for p in data_files],
        ],
        capture_output=True,
        text=True,
    )
    if result.returncode == 0:
        return []

    output = (result.stdout + result.stderr).strip()
    lines = [ln for ln in output.splitlines() if ln.strip()] or ["validation failed"]
    return [Problem("linkml-validate", line) for line in lines]


def check_governance(glossary: Glossary) -> list[Problem]:
    """Rules LinkML expressions cannot state."""
    problems: list[Problem] = []

    for item in [*glossary.terms, *glossary.areas]:
        if not VALID_ID.match(item.id):
            problems.append(
                Problem(
                    f"{item.source_file} / {item.id}",
                    f"{item.id!r} is not a usable CURIE. It expands to an IRI "
                    "that will not resolve -- remove spaces and any other "
                    "character not allowed in an IRI (e.g. unmc:ResearchProject).",
                )
            )

    for term in glossary.terms:
        where = f"{term.source_file} / {term.id}"
        owners = [r for r in term.responsibilities if r.role == "definition_owner"]
        if len(owners) != 1:
            problems.append(
                Problem(
                    where,
                    f"needs exactly one definition_owner, found {len(owners)}. "
                    "Accountability has to land on one office.",
                )
            )

        for role, holders in _by_role(term.responsibilities).items():
            if len(holders) > 1:
                names = ", ".join(sorted(h.agent.pref_label for h in holders))
                problems.append(
                    Problem(
                        where,
                        f"has {len(holders)} offices holding {ROLE_LABELS.get(role, role)} "
                        f"({names}). Split the term or pick one.",
                    )
                )

        # No rule requiring `definition_source` on an approved term. The slot
        # means "adopted from elsewhere", so a definition UNMC authored itself
        # correctly has none, and demanding one would force stewards to invent
        # a URL. Approval is evidenced by the merged pull request.

        if term.status == "approved" and term.definition.lower().startswith("todo"):
            problems.append(
                Problem(where, "is approved but its definition is still a TODO.")
            )

        if term.status == "deprecated" and term.replaced_by is None:
            problems.append(
                Problem(
                    where,
                    "is deprecated with no replaced_by. A reader hitting this "
                    "term has nowhere to go.",
                )
            )

        if term.replaced_by is not None and term.status != "deprecated":
            problems.append(
                Problem(
                    where,
                    f"has replaced_by set but status is {term.status!r}. "
                    "Only a deprecated term is replaced.",
                )
            )

        if term.replaced_by is not None and term.replaced_by.id == term.id:
            problems.append(Problem(where, "is replaced by itself."))

        for ancestor in _ancestors(term):
            if ancestor.id == term.id:
                problems.append(
                    Problem(where, "is its own broader term, directly or via a cycle.")
                )
                break

    for area in glossary.areas:
        owners = [r for r in area.responsibilities if r.role == "definition_owner"]
        if len(owners) != 1:
            problems.append(
                Problem(
                    f"{area.source_file} / {area.id}",
                    f"needs exactly one definition_owner, found {len(owners)}.",
                )
            )

    return problems


def warnings(glossary: Glossary) -> list[Problem]:
    """Things worth saying out loud that should not stop a build.

    Registering an office before the term that will name it is a normal
    intermediate state, so an unused agent is reported and then ignored.
    """
    notes: list[Problem] = []

    used_agents = {
        r.agent.id
        for item in [*glossary.terms, *glossary.areas]
        for r in item.responsibilities
    }
    for agent_id, agent in glossary.agents.items():
        if agent_id not in used_agents:
            notes.append(
                Problem(
                    f"agents.yaml / {agent_id}",
                    f"{agent.pref_label} holds no governance role yet.",
                )
            )

    staffed = {p.id for agent in glossary.agents.values() for p in agent.contacts}
    for person_id, person in glossary.people.items():
        if person_id not in staffed:
            notes.append(
                Problem(
                    f"agents.yaml / {person_id}",
                    f"{person.name} staffs no office yet.",
                )
            )

    for term in glossary.terms:
        if term.status in {"approved", "in_review"} and not term.steward:
            notes.append(
                Problem(
                    f"{term.source_file} / {term.id}",
                    "has no data_steward. Nobody is on the hook for the quality "
                    "of the data behind it.",
                )
            )

    return notes


def _by_role(responsibilities):
    out: dict[str, list] = {}
    for r in responsibilities:
        out.setdefault(r.role, []).append(r)
    return out


def _ancestors(term, seen=None):
    """Walk `broader` upward, stopping if we revisit a term."""
    seen = seen or set()
    for parent in term.broader:
        if parent.id in seen:
            yield parent
            return
        seen.add(parent.id)
        yield parent
        yield from _ancestors(parent, seen)
