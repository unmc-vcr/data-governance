"""Loading, cross-references, and the derived fields templates depend on."""

from pathlib import Path

import pytest

from terms_site.model import TermsError, expand_curie, load, slugify

FIXTURES = Path(__file__).parent / "fixtures"


def test_slugify_splits_camel_case():
    assert slugify("unmc:ClinicalTrial") == "clinical-trial"
    assert slugify("office:ClinicalResearchOffice") == "clinical-research-office"
    assert slugify("unmc:IRBProtocolNumber") == "irb-protocol-number"


def test_expand_curie():
    prefixes = {"term": "https://example.edu/terms/"}
    assert expand_curie("term:Foo", prefixes) == "https://example.edu/terms/Foo"
    # Unknown prefix stays visible rather than becoming a wrong IRI.
    assert expand_curie("other:Foo", prefixes) == "other:Foo"
    assert expand_curie("https://example.org/x", prefixes) == "https://example.org/x"


def test_loads_all_terms_and_areas(termset):
    assert [a.pref_label for a in termset.areas] == ["Alpha Area", "Beta Area"]
    assert [t.pref_label for t in termset.terms] == [
        "Beta Term",
        "Fully Loaded",
        "Narrower Thing",
        "Old Thing",
    ]


def test_each_term_is_attributed_to_its_own_file(termset):
    """The point of the per-term layout: a term's source_file drives both its
    GitHub source link and which commits count as its history. If two terms
    shared a file, editing one would show up in the other's timeline."""
    sources = {t.id: t.source_file for t in termset.terms}
    assert sources["term:FullyLoaded"].endswith("alpha/terms/fully_loaded.yaml")
    assert sources["term:BetaTerm"].endswith("beta/terms/beta_term.yaml")
    assert len(set(sources.values())) == len(sources), "terms share a file"

    # Subject areas are declared separately from their terms.
    areas = {a.id: a.source_file for a in termset.areas}
    assert areas["area:Alpha"].endswith("alpha/alpha.yaml")
    assert not set(areas.values()) & set(sources.values())


def test_broader_is_inverted_into_narrower(termset):
    full = termset.term_by_id("term:FullyLoaded")
    narrower = termset.term_by_id("term:NarrowerThing")
    assert narrower.broader == [full]
    assert full.narrower == [narrower]


def test_replaced_by_is_inverted_into_replaces(termset):
    full = termset.term_by_id("term:FullyLoaded")
    old = termset.term_by_id("term:OldThing")
    assert old.replaced_by is full
    assert full.replaces == [old]


def test_responsibilities_resolve_to_agents_and_sort_by_role(termset):
    full = termset.term_by_id("term:FullyLoaded")
    assert [r.role for r in full.responsibilities] == ["definition_owner", "data_steward"]
    assert full.owner.pref_label == "Office A"
    assert full.steward.pref_label == "Office B"
    assert full.steward.email == "office-b@example.edu"


def test_agent_initials(termset):
    assert termset.agents["office:OfficeA"].initials == "OA"


def test_related_terms_are_labelled(termset):
    full = termset.term_by_id("term:FullyLoaded")
    related = {t.pref_label: rel for t, rel in full.related}
    assert related == {
        "Narrower Thing": "Narrower term",
        "Old Thing": "Replaced by this term",
    }


def test_handling_matrix_follows_classification(termset):
    full = termset.term_by_id("term:FullyLoaded")
    assert dict(full.handling)["Email"] == "Encrypted only"
    narrower = termset.term_by_id("term:NarrowerThing")
    assert narrower.handling == []


def test_iri_expands(termset):
    assert (
        termset.term_by_id("term:FullyLoaded").iri
        == "https://example.edu/terms/FullyLoaded"
    )


def test_search_text_includes_alt_labels(termset):
    text = termset.term_by_id("term:FullyLoaded").search_text()
    assert "Kitchen Sink" in text
    assert "AL.FUL.001" in text


def test_counts(termset):
    assert termset.counts == {
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
      - {agent: 'office:OfficeA', governance_role: definition_owner}
terms:
  - id: unmc:T
    pref_label: T
    definition: d
    in_subject_area: unmc:A
    broader: [unmc:DoesNotExist]
    responsibilities:
      - {agent: 'office:OfficeA', governance_role: definition_owner}
    status: draft
""",
    )
    with pytest.raises(TermsError, match="broader term 'unmc:DoesNotExist'"):
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
      - {agent: 'office:Nobody', governance_role: definition_owner}
terms: []
""",
    )
    with pytest.raises(TermsError, match="office:Nobody"):
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
      - {agent: 'office:OfficeA', governance_role: definition_owner}
    status: draft
""",
    )
    with pytest.raises(TermsError, match="in_subject_area 'unmc:Missing'"):
        load([bad], fixture_agents, tmp_path)


def test_page_url_collision_is_an_error(tmp_path, fixture_agents):
    bad = _write(
        tmp_path,
        "bad.yaml",
        """
subject_areas:
  - id: unmc:A
    pref_label: A
    definition: d
    responsibilities:
      - {agent: 'office:OfficeA', governance_role: definition_owner}
terms:
  - id: unmc:FooBar
    pref_label: One
    definition: d
    in_subject_area: unmc:A
    responsibilities:
      - {agent: 'office:OfficeA', governance_role: definition_owner}
    status: draft
  - id: unmc:foo/FooBar
    pref_label: Two
    definition: d
    in_subject_area: unmc:A
    responsibilities:
      - {agent: 'office:OfficeA', governance_role: definition_owner}
    status: draft
""",
    )
    with pytest.raises(TermsError, match="both resolve to the page"):
        load([bad], fixture_agents, tmp_path)
