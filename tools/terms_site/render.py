"""Jinja environment, navigation, and page rendering."""

from __future__ import annotations

import hashlib
import json
import re
import shutil
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from urllib.parse import urlparse

import yaml
from jinja2 import Environment, FileSystemLoader, StrictUndefined, select_autoescape

from .content import ContentPage
from .model import (
    CLASSIFICATION_LABELS,
    TermSet,
    ROLE_LABELS,
    STATUS_LABELS,
)

# Schema elements are published here rather than under "reference/", so that
# the site path matches the IRI sub-path: an element minted as
# `unmc:Term` expands to https://w3id.org/unmc/model/Term and resolves to
# /model/Term.html. That keeps the w3id .htaccess to one generic rule -- the
# IRI path is the site path plus ".html" -- instead of needing a special case.
SCHEMA_DIR = "model"

TEMPLATES = Path(__file__).parent / "templates"
STATIC = Path(__file__).parent / "static"

ROLE_COLOURS = {
    "definition_owner": "var(--navy)",
    "data_steward": "var(--teal)",
    "business_sme": "var(--ink-3)",
}

# Order of Term slots on the "How to read a term" page. Follows the order a
# reader meets them on an actual term page rather than the schema's order.
FIELD_ORDER = [
    "pref_label",
    "alt_labels",
    "code",
    "definition",
    "definition_source",
    "status",
    "in_subject_area",
    "classification",
    "responsibilities",
    "rules",
    "source_of_record",
    "used_in",
    "broader",
    "replaced_by",
    "exact_match",
    "close_match",
    "realized_by",
    "guidance",
]

FIELD_LABELS = {
    "pref_label": "Name",
    "alt_labels": "Also called",
    "code": "Code",
    "definition": "Definition",
    "definition_source": "Definition source",
    "status": "Status",
    "in_subject_area": "Subject area",
    "classification": "Classification",
    "responsibilities": "Responsibility",
    "rules": "Rules & qualifiers",
    "source_of_record": "Source of record",
    "used_in": "Where it is used",
    "broader": "Broader term",
    "replaced_by": "Replaced by",
    "exact_match": "Same as",
    "close_match": "Similar to",
    "realized_by": "Implemented in",
    "guidance": "Callouts",
}


@dataclass
class NavItem:
    label: str
    url: str


@dataclass
class NavGroup:
    label: str
    items: list[NavItem]


def _domain(url: str) -> str:
    try:
        host = urlparse(url).netloc
    except ValueError:
        return url
    return host.removeprefix("www.") or url


def _as_link(value: str) -> str:
    """Render a CURIE or URL as a link when it is dereferenceable."""
    if value.startswith(("http://", "https://")):
        return f'<a href="{value}" rel="noopener">{value}</a>'
    return f'<code class="term-code">{value}</code>'


def _badge_slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_")


def _asset_version() -> str:
    """Short digest of the static assets, appended to their URLs.

    Without this, a browser that cached site.css keeps using it after a
    deploy, so a steward reloading the site sees new content in old styling.
    The digest only changes when an asset changes, so caching still works.
    """
    digest = hashlib.sha256()
    for item in sorted(STATIC.iterdir()):
        if item.is_file():
            digest.update(item.read_bytes())
    return digest.hexdigest()[:10]


def _rel_for(out_path: str) -> str:
    """Relative prefix from a page back to the site root."""
    depth = out_path.count("/")
    return "../" * depth


def make_env() -> Environment:
    env = Environment(
        loader=FileSystemLoader(str(TEMPLATES)),
        autoescape=select_autoescape(["html", "j2"]),
        undefined=StrictUndefined,
        trim_blocks=True,
        lstrip_blocks=True,
    )
    env.filters["domain"] = _domain
    env.filters["as_link"] = _as_link
    env.filters["badge_slug"] = _badge_slug
    env.filters["role_colour"] = lambda role: ROLE_COLOURS.get(role, "var(--ink-3)")
    return env


def build_nav(pages: list[ContentPage], has_reference: bool) -> list[NavGroup]:
    """Sidebar nav: authored groups first, then the generated reference."""
    groups: dict[str, list[tuple[int, NavItem]]] = {}
    group_order: list[str] = []

    for page in pages:
        if page.is_hub or not page.nav_group:
            continue
        if page.nav_group not in groups:
            groups[page.nav_group] = []
            group_order.append(page.nav_group)
        groups[page.nav_group].append((page.order, NavItem(page.nav_label, page.url)))

    nav = [
        NavGroup(
            label="Start here",
            items=[NavItem("Governance home", "index.html")]
            + [
                item
                for _, item in sorted(groups.pop("Start here", []), key=lambda p: p[0])
            ],
        )
    ]
    if "Start here" in group_order:
        group_order.remove("Start here")

    for label in group_order:
        nav.append(
            NavGroup(
                label=label,
                items=[item for _, item in sorted(groups[label], key=lambda p: p[0])],
            )
        )

    # Subject areas are deliberately not listed here: they are reachable from
    # the term index, and duplicating them in the sidebar makes the nav grow
    # without bound as subject areas are added.
    reference_items = [
        NavItem("Data Dictionary", "terms/index.html"),
        NavItem("Offices", "offices/index.html"),
        NavItem("How to read a term", "how-to-read-a-term.html"),
    ]
    nav.append(NavGroup(label="Reference", items=reference_items))

    if has_reference:
        nav.append(
            NavGroup(
                label="System",
                items=[NavItem("Schema reference", f"{SCHEMA_DIR}/index.html")],
            )
        )

    return nav


class Renderer:
    def __init__(
        self,
        out_dir: Path,
        termset: TermSet,
        nav: list[NavGroup],
        schema: dict,
        *,
        contact_email: str,
        suggest_change_url: str | None,
        repo_blob_url: str | None = None,
        base_path: str = "/",
    ) -> None:
        self.out = out_dir
        self.env = make_env()
        self.termset = termset
        self.nav = nav
        self.schema = schema
        self.contact_email = contact_email
        self.suggest_change_url = suggest_change_url
        self.repo_blob_url = repo_blob_url
        # Where the site is served from. "/" for a custom domain,
        # "/<repo>/" for a GitHub Pages project site. Only 404.html needs
        # it; every other page computes its own relative prefix.
        self.base_path = base_path if base_path.endswith("/") else base_path + "/"
        self.built_on = date.today().strftime("%d %b %Y")
        self.written: list[str] = []
        self.asset_version = _asset_version()

    def _base_context(self, out_path: str, title: str, breadcrumb=None, description=None):
        return {
            "rel": _rel_for(out_path),
            "current_url": out_path,
            "nav": self.nav,
            "page_title": title,
            "page_description": description,
            "breadcrumb": breadcrumb or [],
            "built_on": self.built_on,
            "contact_email": self.contact_email,
            "schema_name": self.schema.get("name", "unmc_terms"),
            "schema_version": self.schema.get("version", "0"),
            "suggest_change_url": self.suggest_change_url,
            "repo_blob_url": self.repo_blob_url,
            "asset_version": self.asset_version,
        }

    def write(self, out_path: str, template: str, **context) -> None:
        destination = self.out / out_path
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(self.env.get_template(template).render(**context), encoding="utf-8")
        self.written.append(out_path)

    # ---------- pages ----------

    def hub(self, page: ContentPage, recent_changes, contacts) -> None:
        counts = self.termset.counts
        stats = [
            {"n": counts.get("approved", 0), "label": "Approved terms in the dictionary"},
            {"n": len(self.termset.areas), "label": "Subject areas under governance"},
            {"n": len(self.termset.agents), "label": "Offices holding a governance role"},
            {
                "n": counts.get("draft", 0) + counts.get("in_review", 0),
                "label": "Terms under review",
            },
        ]
        self.write(
            "index.html",
            "hub.html.j2",
            page=page,
            stats=stats,
            areas=self.termset.areas,
            recent_changes=recent_changes,
            contacts=contacts,
            **self._base_context("index.html", page.title, description=page.lede),
        )

    def terms_index(self) -> None:
        self.write(
            "terms/index.html",
            "terms_index.html.j2",
            terms=self.termset.terms,
            areas=self.termset.areas,
            **self._base_context(
                "terms/index.html",
                "Data dictionary",
                breadcrumb=[{"label": "Terms", "url": None}],
                description="Every governed business term at UNMC, with its definition, status, and accountable office.",
            ),
        )

    def term_page(self, term) -> None:
        self.write(
            term.url,
            "term.html.j2",
            term=term,
            **self._base_context(
                term.url,
                term.pref_label,
                breadcrumb=[
                    {"label": "Terms", "url": "terms/index.html"},
                    {"label": term.area.pref_label, "url": term.area.url},
                    {"label": term.pref_label, "url": None},
                ],
                description=term.definition[:180],
            ),
        )

    def area_page(self, area) -> None:
        counts: dict[str, int] = {}
        for term in area.terms:
            counts[term.status_label] = counts.get(term.status_label, 0) + 1
        ordered = [
            (label, counts[label])
            for label in STATUS_LABELS.values()
            if label in counts
        ]
        self.write(
            area.url,
            "area.html.j2",
            area=area,
            status_counts=ordered,
            **self._base_context(
                area.url,
                area.pref_label,
                breadcrumb=[
                    {"label": "Terms", "url": "terms/index.html"},
                    {"label": area.pref_label, "url": None},
                ],
                description=area.definition[:180],
            ),
        )

    def office_page(self, office) -> None:
        # `roles` reflects everything the office does, area- or term-level, so
        # the meta row is complete. The "Accountable for" list, though, stays
        # at the subject-area level: listing every term makes the sidebar grow
        # without bound, and a term's office is reachable from the term itself.
        roles: set[str] = set()
        for items in (self.termset.areas, self.termset.terms):
            for item in items:
                for r in item.responsibilities:
                    if r.agent.id == office.id:
                        roles.add(r.role)

        accountable_for: list[dict] = []
        for area in self.termset.areas:
            for r in area.responsibilities:
                if r.agent.id != office.id:
                    continue
                accountable_for.append(
                    {
                        "label": area.pref_label,
                        "url": area.url,
                        "role_label": ROLE_LABELS.get(r.role, r.role),
                    }
                )
        accountable_for.sort(key=lambda a: a["label"].lower())
        ordered_roles = [
            ROLE_LABELS.get(role, role)
            for role in ("definition_owner", "data_steward", "business_sme")
            if role in roles
        ]
        self.write(
            office.url,
            "office.html.j2",
            office=office,
            roles=ordered_roles,
            accountable_for=accountable_for,
            **self._base_context(
                office.url,
                office.pref_label,
                breadcrumb=[
                    {"label": "Offices", "url": "offices/index.html"},
                    {"label": office.pref_label, "url": None},
                ],
                description=f"Who to contact at {office.pref_label} and the terms it is accountable for.",
            ),
        )

    def content_page(self, page: ContentPage) -> None:
        self.write(
            page.url,
            "page.html.j2",
            page=page,
            **self._base_context(
                page.url,
                page.title,
                breadcrumb=[{"label": page.title, "url": None}],
                description=page.lede,
            ),
        )

    def how_to_read(self, reference_url: str | None) -> None:
        slots = self.schema.get("slots", {})
        term_slots = self.schema.get("classes", {}).get("Term", {}).get("slots", [])
        fields = []
        for name in FIELD_ORDER:
            if name not in term_slots:
                continue
            spec = slots.get(name, {})
            description = (spec.get("description") or "").strip()
            if not description:
                description = f"The term's {FIELD_LABELS.get(name, name).lower()}."
            fields.append(
                {
                    "label": FIELD_LABELS.get(name, name.replace("_", " ").title()),
                    "description": " ".join(description.split()),
                    "required": bool(spec.get("required")),
                    "uri": spec.get("slot_uri"),
                }
            )

        def enum_values(enum_name: str, labels: dict[str, str]):
            values = self.schema.get("enums", {}).get(enum_name, {}).get("permissible_values", {})
            return [
                {
                    "name": key,
                    "label": labels.get(key, key.replace("_", " ").title()),
                    "description": " ".join((spec or {}).get("description", "").split())
                    or "No description recorded in the schema.",
                }
                for key, spec in values.items()
            ]

        self.write(
            "how-to-read-a-term.html",
            "how_to_read.html.j2",
            fields=fields,
            statuses=enum_values("TermStatus", STATUS_LABELS),
            roles=enum_values("GovernanceRole", ROLE_LABELS),
            classifications=enum_values("DataClassification", CLASSIFICATION_LABELS),
            reference_url=reference_url,
            **self._base_context(
                "how-to-read-a-term.html",
                "How to read a term",
                breadcrumb=[{"label": "How to read a term", "url": None}],
                description="What each field on a term page means.",
            ),
        )

    def offices_index(self) -> None:
        # Every office that holds a governance role somewhere in the term data,
        # with the roles it holds and how much it is accountable for. Offices in
        # the registry that no term or area names are left off: the page is an
        # index of offices *mentioned in the terms*, not the raw registry.
        offices = []
        for office in self.termset.agents.values():
            roles: set[str] = set()
            term_count = 0
            area_count = 0
            for term in self.termset.terms:
                held = [r.role for r in term.responsibilities if r.agent.id == office.id]
                if held:
                    term_count += 1
                    roles.update(held)
            for area in self.termset.areas:
                held = [r.role for r in area.responsibilities if r.agent.id == office.id]
                if held:
                    area_count += 1
                    roles.update(held)
            if not roles:
                continue
            offices.append(
                {
                    "office": office,
                    "roles": [ROLE_LABELS[r] for r in ROLE_LABELS if r in roles],
                    "term_count": term_count,
                    "area_count": area_count,
                }
            )
        offices.sort(key=lambda o: o["office"].pref_label.lower())

        self.write(
            "offices/index.html",
            "offices_index.html.j2",
            offices=offices,
            **self._base_context(
                "offices/index.html",
                "Offices",
                breadcrumb=[{"label": "Offices", "url": None}],
                description="Every office that holds a governance role for a UNMC business term, with its roles and what it is accountable for.",
            ),
        )

    def not_found_page(self) -> None:
        """Served by GitHub Pages for any unmatched URL under the site."""
        self.write(
            "404.html",
            "not_found.html.j2",
            asset_version=self.asset_version,
            contact_email=self.contact_email,
            base_path=self.base_path,
        )

    def reference_page(
        self, out_path: str, title: str, body: str, siblings, *, has_diagram: bool = False
    ) -> None:
        self.write(
            out_path,
            "reference.html.j2",
            body=body,
            siblings=siblings,
            has_diagram=has_diagram,
            **self._base_context(
                out_path,
                title,
                breadcrumb=[
                    {"label": "Schema reference", "url": f"{SCHEMA_DIR}/index.html"},
                    {"label": title, "url": None},
                ],
            ),
        )

    # ---------- assets ----------

    def copy_static(self) -> None:
        assets = self.out / "assets"
        assets.mkdir(parents=True, exist_ok=True)
        for item in STATIC.iterdir():
            if item.is_file():
                shutil.copy2(item, assets / item.name)

    def write_search_index(self, pages: list[ContentPage]) -> None:
        entries = []

        for term in self.termset.terms:
            entries.append(
                {
                    "kind": "term",
                    "kindLabel": "Term",
                    "title": term.pref_label,
                    "alt": term.alt_labels,
                    "url": term.url,
                    "path": f"Terms / {term.area.pref_label}",
                    "meta": f"{term.status_label}"
                    + (f" · Steward: {term.steward.pref_label}" if term.steward else ""),
                    "snippet": term.definition,
                    "text": term.search_text(),
                }
            )

        for area in self.termset.areas:
            entries.append(
                {
                    "kind": "area",
                    "kindLabel": "Subject area",
                    "title": area.pref_label,
                    "alt": [],
                    "url": area.url,
                    "path": "Terms",
                    "meta": f"{len(area.terms)} term{'' if len(area.terms) == 1 else 's'}"
                    + (f" · {area.owner.pref_label}" if area.owner else ""),
                    "snippet": area.definition,
                    "text": f"{area.pref_label} {area.definition}",
                }
            )

        for office in self.termset.agents.values():
            names = [c.name for c in office.contacts]
            entries.append(
                {
                    "kind": "office",
                    "kindLabel": "Office",
                    "title": office.pref_label,
                    "alt": names,
                    "url": office.url,
                    "path": "Terms",
                    "meta": office.email or "",
                    "snippet": "Who to contact and the terms this office is accountable for."
                    + (f" Contacts: {', '.join(names)}." if names else ""),
                    "text": f"{office.pref_label} {office.email or ''} {' '.join(names)}",
                }
            )

        for page in pages:
            entries.append(
                {
                    "kind": "page",
                    "kindLabel": "Standard or guide",
                    "title": page.title,
                    "alt": [],
                    "url": page.url,
                    "path": page.nav_group or "Research Administration Data Governance",
                    "meta": " · ".join(page.meta) if page.meta else "",
                    "snippet": page.lede or page.summary,
                    "text": f"{page.title} {page.lede or ''} {page.summary}",
                }
            )

        destination = self.out / "assets" / "search-index.json"
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(
            json.dumps(entries, ensure_ascii=False, separators=(",", ":")), encoding="utf-8"
        )


def load_schema(path: Path) -> dict:
    with path.open(encoding="utf-8") as fh:
        return yaml.safe_load(fh) or {}
