"""Load term YAML into the shape the templates want.

The YAML is validated separately by `linkml-validate` (see checks.validate),
so this module assumes well-formed input and concerns itself with the things
validation cannot do: resolving cross-references, inverting `broader` into
`narrower`, grouping responsibilities by role, and assigning URLs.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

import yaml

# Presentation-only accent assignment. Subject areas get a stable colour from
# this cycle so the hub cards and area pages agree with each other; the colour
# is not governed data and deliberately does not live in the schema.
ACCENTS = ["var(--teal)", "var(--navy)", "var(--red)", "var(--blue)", "var(--olive)"]

ROLE_ORDER = ["definition_owner", "data_steward", "business_sme"]

ROLE_LABELS = {
    "definition_owner": "Definition Owner",
    "data_steward": "Data Steward",
    "business_sme": "Business SME",
}

STATUS_LABELS = {
    "draft": "Draft",
    "in_review": "In Review",
    "approved": "Approved",
    "deprecated": "Deprecated",
}

CLASSIFICATION_LABELS = {
    "public": "Public",
    "internal": "Internal",
    "sensitive": "Sensitive",
    "restricted": "Restricted",
}

GUIDANCE_LABELS = {
    "required": "Required",
    "good_to_know": "Good to know",
    "in_review": "In review",
    "draft": "Draft",
}

# Handling matrix from the site design. PROVISIONAL -- see the note on
# DataClassification in the schema. Rendered with a provisional marker.
HANDLING = {
    "public": [
        ("Storage", "Anywhere"),
        ("Sharing", "Permitted"),
        ("Email", "Permitted"),
        ("Retention", "Indefinite"),
    ],
    "internal": [
        ("Storage", "University systems"),
        ("Sharing", "With agreement"),
        ("Email", "Permitted"),
        ("Retention", "7 years"),
    ],
    "sensitive": [
        ("Storage", "Approved systems"),
        ("Sharing", "DUA required"),
        ("Email", "Encrypted only"),
        ("Retention", "Per protocol"),
    ],
    "restricted": [
        ("Storage", "Enclave only"),
        ("Sharing", "IRB + DUA"),
        ("Email", "Prohibited"),
        ("Retention", "Per protocol"),
    ],
}


class TermsError(Exception):
    """Raised when the term data cannot be assembled into a site."""


def expand_curie(value: str, prefixes: dict[str, str]) -> str:
    """`unmc:ClinicalTrial` -> `https://w3id.org/unmc/terms/ClinicalTrial`."""
    if value.startswith(("http://", "https://")):
        return value
    prefix, _, local = value.partition(":")
    base = prefixes.get(prefix)
    if not base or not local:
        return value
    return base + local


def slugify(value: str) -> str:
    """Turn a CURIE or label into a URL-safe slug.

    `unmc:ClinicalTrial` becomes `clinical-trial`; the prefix is dropped
    because term pages already live under /terms/.
    """
    local = value.split(":")[-1].split("/")[-1]
    # Split CamelCase before lowercasing, so ClinicalTrial -> clinical-trial.
    # The second pattern breaks an acronym off the word that follows it, so
    # IRBProtocolNumber -> irb-protocol-number rather than irbprotocol-number.
    spaced = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", "-", local)
    spaced = re.sub(r"(?<=[A-Z])(?=[A-Z][a-z])", "-", spaced)
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", spaced).strip("-").lower()
    if not slug:
        raise TermsError(f"cannot build a slug from {value!r}")
    return slug


def _initials(text: str) -> str:
    words = [w for w in re.split(r"[\s&]+", text) if w and w[0].isalpha()]
    return "".join(w[0] for w in words[:2]).upper() or "??"


@dataclass
class Person:
    """A named individual who staffs one or more offices.

    People are a directory, never the target of a Responsibility. A term is
    owned by an office; the office resolves to whoever currently staffs it, so
    ownership survives staff turnover. See Agent.
    """

    id: str
    name: str
    email: str | None = None
    title: str | None = None

    @property
    def initials(self) -> str:
        return _initials(self.name)


@dataclass
class Agent:
    id: str
    pref_label: str
    email: str | None = None
    contacts: list[Person] = field(default_factory=list)

    @property
    def initials(self) -> str:
        return _initials(self.pref_label)

    @property
    def slug(self) -> str:
        return slugify(self.id)

    @property
    def url(self) -> str:
        return f"offices/{self.slug}.html"


@dataclass
class Responsibility:
    role: str
    agent: Agent

    @property
    def role_label(self) -> str:
        return ROLE_LABELS.get(self.role, self.role.replace("_", " ").title())


@dataclass
class Change:
    """One entry in a term's change history, derived from git."""

    date: str
    iso: str
    author: str
    summary: str
    commit: str


@dataclass
class SubjectArea:
    id: str
    pref_label: str
    definition: str
    responsibilities: list[Responsibility] = field(default_factory=list)
    accent: str = ACCENTS[0]
    source_file: str = ""
    terms: list["Term"] = field(default_factory=list)

    @property
    def slug(self) -> str:
        return slugify(self.id)

    @property
    def url(self) -> str:
        return f"areas/{self.slug}.html"

    @property
    def owner(self) -> Agent | None:
        return next(
            (r.agent for r in self.responsibilities if r.role == "definition_owner"),
            None,
        )


@dataclass
class Term:
    id: str
    pref_label: str
    definition: str
    status: str
    area: SubjectArea
    code: str | None = None
    alt_labels: list[str] = field(default_factory=list)
    definition_source: str | None = None
    classification: str | None = None
    source_of_record: dict | None = None
    rules: list[str] = field(default_factory=list)
    used_in: list[dict] = field(default_factory=list)
    guidance: list[dict] = field(default_factory=list)
    responsibilities: list[Responsibility] = field(default_factory=list)
    exact_match: list[str] = field(default_factory=list)
    close_match: list[str] = field(default_factory=list)
    realized_by: list[str] = field(default_factory=list)
    broader: list["Term"] = field(default_factory=list)
    narrower: list["Term"] = field(default_factory=list)
    replaced_by: "Term | None" = None
    replaces: list["Term"] = field(default_factory=list)
    history: list[Change] = field(default_factory=list)
    source_file: str = ""
    prefixes: dict[str, str] = field(default_factory=dict)

    @property
    def slug(self) -> str:
        return slugify(self.id)

    @property
    def iri(self) -> str:
        """The term's CURIE expanded to a full IRI, for citation.

        Falls back to the CURIE when the prefix is unknown, which is visibly
        wrong on the page rather than silently wrong in someone's citation.
        """
        return expand_curie(self.id, self.prefixes)

    @property
    def local_id(self) -> str:
        """The identifier's local part, e.g. `unmc:Award` -> `Award`.

        This, not the kebab slug, is what the page URL uses, so that the page
        path matches the term's IRI exactly: `unmc:Award` expands to
        `https://w3id.org/unmc/terms/Award` and is served at `/terms/Award`.
        A w3id redirect from the namespace to this site is then the only thing
        needed to make every term IRI dereference.
        """
        return self.id.split(":")[-1].split("/")[-1]

    @property
    def url(self) -> str:
        return f"terms/{self.local_id}.html"

    @property
    def status_label(self) -> str:
        return STATUS_LABELS.get(self.status, self.status)

    @property
    def classification_label(self) -> str | None:
        if not self.classification:
            return None
        return CLASSIFICATION_LABELS.get(self.classification, self.classification)

    @property
    def handling(self) -> list[tuple[str, str]]:
        return HANDLING.get(self.classification or "", [])

    @property
    def owner(self) -> Agent | None:
        return next(
            (r.agent for r in self.responsibilities if r.role == "definition_owner"),
            None,
        )

    @property
    def steward(self) -> Agent | None:
        return next(
            (r.agent for r in self.responsibilities if r.role == "data_steward"),
            None,
        )

    @property
    def last_changed(self) -> str | None:
        return self.history[0].date if self.history else None

    @property
    def related(self) -> list[tuple["Term", str]]:
        """Terms worth a sidebar link, with why they are related."""
        out: list[tuple[Term, str]] = []
        seen = {self.id}
        for t in self.broader:
            if t.id not in seen:
                out.append((t, "Broader term"))
                seen.add(t.id)
        for t in self.narrower:
            if t.id not in seen:
                out.append((t, "Narrower term"))
                seen.add(t.id)
        if self.replaced_by and self.replaced_by.id not in seen:
            out.append((self.replaced_by, "Replaces this term"))
            seen.add(self.replaced_by.id)
        for t in self.replaces:
            if t.id not in seen:
                out.append((t, "Replaced by this term"))
                seen.add(t.id)
        return out

    def search_text(self) -> str:
        parts = [self.pref_label, *self.alt_labels, self.definition, self.area.pref_label]
        if self.code:
            parts.append(self.code)
        parts.extend(self.rules)
        return " ".join(p for p in parts if p)


@dataclass
class TermSet:
    areas: list[SubjectArea]
    terms: list[Term]
    agents: dict[str, Agent]
    people: dict[str, Person] = field(default_factory=dict)
    prefixes: dict[str, str] = field(default_factory=dict)

    def term_by_id(self, term_id: str) -> Term | None:
        return next((t for t in self.terms if t.id == term_id), None)

    @property
    def counts(self) -> dict[str, int]:
        out = {"approved": 0, "in_review": 0, "draft": 0, "deprecated": 0}
        for t in self.terms:
            out[t.status] = out.get(t.status, 0) + 1
        return out


def _read(path: Path) -> dict:
    with path.open(encoding="utf-8") as fh:
        data = yaml.safe_load(fh) or {}
    if not isinstance(data, dict):
        raise TermsError(f"{path}: expected a mapping at the top level")
    return data


def load(
    definition_paths: list[Path],
    agents_path: Path,
    repo_root: Path,
    prefixes: dict[str, str] | None = None,
) -> TermSet:
    """Assemble a TermSet from the definition files and the agent registry.

    Raises TermsError on any dangling reference. `linkml-validate` does not
    catch these -- it validates shapes, not the graph -- so they are caught
    here and fail the build.
    """
    prefixes = prefixes or {}
    registry = _read(agents_path)

    people: dict[str, Person] = {}
    for raw in registry.get("people") or []:
        person = Person(
            id=raw["id"],
            name=raw["name"],
            email=raw.get("email"),
            title=raw.get("title"),
        )
        if person.id in people:
            raise TermsError(f"{agents_path}: duplicate person {person.id}")
        people[person.id] = person

    agents: dict[str, Agent] = {}
    for raw in registry.get("agents") or []:
        contacts = []
        for person_id in raw.get("contacts") or []:
            person = people.get(person_id)
            if person is None:
                raise TermsError(
                    f"{agents_path}: agent {raw['id']} lists contact {person_id!r}, "
                    "which is not in the people registry. Add the person there, "
                    "or fix the IRI."
                )
            contacts.append(person)
        agent = Agent(
            id=raw["id"],
            pref_label=raw["pref_label"],
            email=raw.get("email"),
            contacts=contacts,
        )
        if agent.id in agents:
            raise TermsError(f"{agents_path}: duplicate agent {agent.id}")
        agents[agent.id] = agent

    def resolve_responsibilities(raw_list, where: str) -> list[Responsibility]:
        out = []
        for entry in raw_list or []:
            agent_id = entry["agent"]
            agent = agents.get(agent_id)
            if agent is None:
                raise TermsError(
                    f"{where}: agent {agent_id!r} is not in {agents_path.name}. "
                    "Add the office there, or fix the IRI."
                )
            out.append(Responsibility(role=entry["governance_role"], agent=agent))
        out.sort(key=lambda r: ROLE_ORDER.index(r.role) if r.role in ROLE_ORDER else 99)
        return out

    areas: dict[str, SubjectArea] = {}
    raw_terms: list[tuple[dict, Path]] = []

    for path in sorted(definition_paths):
        rel = str(path.relative_to(repo_root))
        doc = _read(path)
        for raw in doc.get("subject_areas") or []:
            if raw["id"] in areas:
                raise TermsError(f"{rel}: subject area {raw['id']} already defined")
            areas[raw["id"]] = SubjectArea(
                id=raw["id"],
                pref_label=raw["pref_label"],
                definition=raw.get("definition", ""),
                responsibilities=resolve_responsibilities(
                    raw.get("responsibilities"), f"{rel} / {raw['id']}"
                ),
                source_file=rel,
            )
        for raw in doc.get("terms") or []:
            raw_terms.append((raw, path))

    for index, area in enumerate(areas.values()):
        area.accent = ACCENTS[index % len(ACCENTS)]

    terms: dict[str, Term] = {}
    for raw, path in raw_terms:
        rel = str(path.relative_to(repo_root))
        area_id = raw["in_subject_area"]
        area = areas.get(area_id)
        if area is None:
            raise TermsError(
                f"{rel} / {raw['id']}: in_subject_area {area_id!r} is not defined "
                "in any definition file."
            )
        if raw["id"] in terms:
            raise TermsError(f"{rel}: term {raw['id']} already defined")
        terms[raw["id"]] = Term(
            id=raw["id"],
            pref_label=raw["pref_label"],
            definition=(raw.get("definition") or "").strip(),
            status=raw["status"],
            area=area,
            code=raw.get("code"),
            alt_labels=list(raw.get("alt_labels") or []),
            definition_source=raw.get("definition_source"),
            classification=raw.get("classification"),
            source_of_record=raw.get("source_of_record"),
            rules=list(raw.get("rules") or []),
            used_in=list(raw.get("used_in") or []),
            guidance=[
                {
                    "kind": g["guidance_kind"],
                    "label": GUIDANCE_LABELS.get(g["guidance_kind"], g["guidance_kind"]),
                    "text": g["guidance_text"].strip(),
                }
                for g in raw.get("guidance") or []
            ],
            responsibilities=resolve_responsibilities(
                raw.get("responsibilities"), f"{rel} / {raw['id']}"
            ),
            exact_match=list(raw.get("exact_match") or []),
            close_match=list(raw.get("close_match") or []),
            realized_by=list(raw.get("realized_by") or []),
            source_file=rel,
            prefixes=prefixes,
        )
        # Stashed for the second pass, once every term exists.
        terms[raw["id"]]._raw_broader = list(raw.get("broader") or [])  # type: ignore[attr-defined]
        terms[raw["id"]]._raw_replaced_by = raw.get("replaced_by")  # type: ignore[attr-defined]

    # Second pass: term-to-term links, now that every id is known.
    for term in terms.values():
        for broader_id in term._raw_broader:  # type: ignore[attr-defined]
            target = terms.get(broader_id)
            if target is None:
                raise TermsError(
                    f"{term.source_file} / {term.id}: broader term {broader_id!r} "
                    "does not exist."
                )
            term.broader.append(target)
            target.narrower.append(term)
        replaced_by_id = term._raw_replaced_by  # type: ignore[attr-defined]
        if replaced_by_id:
            target = terms.get(replaced_by_id)
            if target is None:
                raise TermsError(
                    f"{term.source_file} / {term.id}: replaced_by {replaced_by_id!r} "
                    "does not exist."
                )
            term.replaced_by = target
            target.replaces.append(term)

    for term in terms.values():
        del term._raw_broader  # type: ignore[attr-defined]
        del term._raw_replaced_by  # type: ignore[attr-defined]

    ordered_terms = sorted(terms.values(), key=lambda t: t.pref_label.lower())
    for term in ordered_terms:
        term.narrower.sort(key=lambda t: t.pref_label.lower())
        term.area.terms.append(term)

    # A page URL collision silently overwrites one of the two pages. Compared
    # case-insensitively because macOS and Windows filesystems are: `Award`
    # and `award` are distinct IRIs but the same file, and the loser would
    # vanish without any error at build time.
    for kind, items in (("term", ordered_terms), ("subject area", list(areas.values()))):
        seen: dict[str, str] = {}
        for item in items:
            key = item.url.lower()
            if key in seen:
                raise TermsError(
                    f"{kind} {item.id} and {seen[key]} both resolve to the page "
                    f"{item.url!r}; one would overwrite the other."
                )
            seen[key] = item.id

    return TermSet(
        areas=sorted(areas.values(), key=lambda a: a.pref_label.lower()),
        terms=ordered_terms,
        agents=agents,
        people=people,
        prefixes=prefixes,
    )
