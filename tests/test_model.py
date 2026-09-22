"""Loading, cross-references, and the derived fields templates depend on."""

from pathlib import Path

import pytest

from glossary_site.model import GlossaryError, expand_curie, load, slugify

FIXTURES = Path(__file__).parent / "fixtures"


def test_slugify_splits_camel_case():
    assert slugify("unmc:ClinicalTrial") == "clinical-trial"
    assert slugify("unmc:role/ClinicalResearchOffice") == "clinical-research-office"
    assert slugify("unmc:IRBProtocolNumber") == "irb-protocol-number"


def test_expand_curie():
    prefixes = {"unmc": "https://w3id.org/unmc/glossary/"}
    assert expand_curie("unmc:Foo", prefixes) == "https://w3id.org/unmc/glossary/Foo"
    # Unknown prefix stays visible rather than becoming a wrong IRI.
    assert expand_curie("other:Foo", prefixes) == "other:Foo"
    assert expand_curie("https://example.org/x", prefixes) == "https://example.org/x"


def test_loads_all_terms_and_areas(glossary):
    assert [a.pref_label for a in glossary.areas] == ["Alpha Area", "Beta Area"]
    assert [t.pref_label for t in glossary.terms] == [
        "Beta Term",
        "Fully Loaded",
        "Narrower Thing",
        "Old Thing",
    ]


def test_broader_is_inverted_into_narrower(glossary):
    full = glossary.term_by_id("unmc:FullyLoaded")
    narrower = glossary.term_by_id("unmc:NarrowerThing")
    assert narrower.broader == [full]
    assert full.narrower == [narrower]


def test_replaced_by_is_inverted_into_replaces(glossary):
    full = glossary.term_by_id("unmc:FullyLoaded")
    old = glossary.term_by_id("unmc:OldThing")
    assert old.replaced_by is full
    assert full.replaces == [old]


def test_responsibilities_resolve_to_agents_and_sort_by_role(glossary):
    full = glossary.term_by_id("unmc:FullyLoaded")
    assert [r.role for r in full.responsibilities] == ["definition_owner", "data_steward"]
    assert full.owner.pref_label == "Office A"
    assert full.steward.pref_label == "Office B"
    assert full.steward.email == "office-b@example.edu"


def test_agent_initials(glossary):
    assert glossary.agents["unmc:role/OfficeA"].initials == "OA"


def test_related_terms_are_labelled(glossary):
    full = glossary.term_by_id("unmc:FullyLoaded")
    related = {t.pref_label: rel for t, rel in full.related}
    assert related == {
        "Narrower Thing": "Narrower term",
        "Old Thing": "Replaced by this term",
    }


def test_handling_matrix_follows_classification(glossary):
    full = glossary.term_by_id("unmc:FullyLoaded")
    assert dict(full.handling)["Email"] == "Encrypted only"
    narrower = glossary.term_by_id("unmc:NarrowerThing")
    assert narrower.handling == []


def test_iri_expands(glossary):
    assert (
        glossary.term_by_id("unmc:FullyLoaded").iri
        == "https://w3id.org/unmc/glossary/FullyLoaded"
    )


def test_search_text_includes_alt_labels(glossary):
    text = glossary.term_by_id("unmc:FullyLoaded").search_text()
    assert "Kitchen Sink" in text
    assert "AL.FUL.001" in text


def test_counts(glossary):
    assert glossary.counts == {
        "approved": 1,
        "in_review": 1,
        "draft": 1,
        "deprecated": 1,
    }


def _write(tmp_path: Path, name: str, body: str) -> Path:
    path = tmp_path / name
    path.write_text(body, encoding="utf-8")
    return path


def test_dangling_broader_is_an_error(tmp_path, fixture_agents):
    bad = _write(
        tmp_path,
        "bad.yaml",
        """
subject_areas:
  - id: unmc:A
    pref_label: A
    definition: d
    responsibilities:
      - {agent: 'unmc:role/OfficeA', governance_role: definition_owner}
terms:
  - id: unmc:T
    pref_label: T
    definition: d
    in_subject_area: unmc:A
    broader: [unmc:DoesNotExist]
    responsibilities:
      - {agent: 'unmc:role/OfficeA', governance_role: definition_owner}
    status: draft
""",
    )
    with pytest.raises(GlossaryError, match="broader term 'unmc:DoesNotExist'"):
        load([bad], fixture_agents, tmp_path)


def test_unknown_agent_is_an_error(tmp_path, fixture_agents):
    bad = _write(
        tmp_path,
        "bad.yaml",
        """
subject_areas:
  - id: unmc:A
    pref_label: A
    definition: d
    responsibilities:
      - {agent: 'unmc:role/Nobody', governance_role: definition_owner}
terms: []
""",
    )
    with pytest.raises(GlossaryError, match="unmc:role/Nobody"):
        load([bad], fixture_agents, tmp_path)


def test_unknown_subject_area_is_an_error(tmp_path, fixture_agents):
    bad = _write(
        tmp_path,
        "bad.yaml",
        """
subject_areas: []
terms:
  - id: unmc:T
    pref_label: T
    definition: d
    in_subject_area: unmc:Missing
    responsibilities:
      - {agent: 'unmc:role/OfficeA', governance_role: definition_owner}
    status: draft
""",
    )
    with pytest.raises(GlossaryError, match="in_subject_area 'unmc:Missing'"):
        load([bad], fixture_agents, tmp_path)


def test_slug_collision_is_an_error(tmp_path, fixture_agents):
    bad = _write(
        tmp_path,
        "bad.yaml",
        """
subject_areas:
  - id: unmc:A
    pref_label: A
    definition: d
    responsibilities:
      - {agent: 'unmc:role/OfficeA', governance_role: definition_owner}
terms:
  - id: unmc:FooBar
    pref_label: One
    definition: d
    in_subject_area: unmc:A
    responsibilities:
      - {agent: 'unmc:role/OfficeA', governance_role: definition_owner}
    status: draft
  - id: unmc:foo/FooBar
    pref_label: Two
    definition: d
    in_subject_area: unmc:A
    responsibilities:
      - {agent: 'unmc:role/OfficeA', governance_role: definition_owner}
    status: draft
""",
    )
    with pytest.raises(GlossaryError, match="slugify"):
        load([bad], fixture_agents, tmp_path)
