"""The governance rules LinkML cannot express, plus the validator gate."""

from pathlib import Path

import pytest

from glossary_site import checks
from glossary_site.model import GlossaryError, load

FIXTURES = Path(__file__).parent / "fixtures"


def test_fixture_data_passes_governance_checks(glossary):
    assert checks.check_governance(glossary) == []


def test_fixture_data_passes_schema_validation(schema, fixture_definitions, fixture_agents):
    problems = checks.validate_against_schema(
        schema, [*fixture_definitions, fixture_agents], FIXTURES
    )
    assert problems == []


def test_schema_validation_catches_a_bad_enum(schema, tmp_path, fixture_agents):
    bad = tmp_path / "bad.yaml"
    bad.write_text(
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
    responsibilities:
      - {agent: 'unmc:role/OfficeA', governance_role: definition_owner}
    status: not_a_real_status
""",
        encoding="utf-8",
    )
    problems = checks.validate_against_schema(schema, [bad], tmp_path)
    assert problems, "linkml-validate should reject an unknown status"
    assert any("not_a_real_status" in str(p) for p in problems)


def _load(tmp_path, body, fixture_agents):
    path = tmp_path / "case.yaml"
    path.write_text(body, encoding="utf-8")
    return load([path], fixture_agents, tmp_path)


AREA = """
subject_areas:
  - id: unmc:A
    pref_label: A
    definition: d
    responsibilities:
      - {agent: 'unmc:role/OfficeA', governance_role: definition_owner}
terms:
"""


def test_term_needs_exactly_one_definition_owner(tmp_path, fixture_agents):
    g = _load(
        tmp_path,
        AREA
        + """
  - id: unmc:T
    pref_label: T
    definition: d
    in_subject_area: unmc:A
    responsibilities:
      - {agent: 'unmc:role/OfficeA', governance_role: data_steward}
    status: draft
""",
        fixture_agents,
    )
    assert any("exactly one definition_owner" in str(p) for p in checks.check_governance(g))


def test_two_offices_in_the_same_role_is_flagged(tmp_path, fixture_agents):
    g = _load(
        tmp_path,
        AREA
        + """
  - id: unmc:T
    pref_label: T
    definition: d
    in_subject_area: unmc:A
    responsibilities:
      - {agent: 'unmc:role/OfficeA', governance_role: definition_owner}
      - {agent: 'unmc:role/OfficeB', governance_role: definition_owner}
    status: draft
""",
        fixture_agents,
    )
    problems = [str(p) for p in checks.check_governance(g)]
    assert any("exactly one definition_owner" in p for p in problems)


def test_approved_term_needs_no_definition_source(tmp_path, fixture_agents):
    """`definition_source` means "adopted from elsewhere", so a definition
    authored at UNMC correctly has none. Requiring one would force stewards to
    invent a URL to get a finished definition approved."""
    g = _load(
        tmp_path,
        AREA
        + """
  - id: unmc:T
    pref_label: T
    definition: A definition written here rather than adopted.
    in_subject_area: unmc:A
    responsibilities:
      - {agent: 'unmc:role/OfficeA', governance_role: definition_owner}
    status: approved
""",
        fixture_agents,
    )
    assert checks.check_governance(g) == []


def test_approved_term_cannot_be_a_todo(tmp_path, fixture_agents):
    g = _load(
        tmp_path,
        AREA
        + """
  - id: unmc:T
    pref_label: T
    definition: TODO write this
    definition_source: https://example.edu/s
    in_subject_area: unmc:A
    responsibilities:
      - {agent: 'unmc:role/OfficeA', governance_role: definition_owner}
    status: approved
""",
        fixture_agents,
    )
    assert any("still a TODO" in str(p) for p in checks.check_governance(g))


def test_deprecated_term_needs_a_replacement(tmp_path, fixture_agents):
    g = _load(
        tmp_path,
        AREA
        + """
  - id: unmc:T
    pref_label: T
    definition: d
    in_subject_area: unmc:A
    responsibilities:
      - {agent: 'unmc:role/OfficeA', governance_role: definition_owner}
    status: deprecated
""",
        fixture_agents,
    )
    assert any("no replaced_by" in str(p) for p in checks.check_governance(g))


def test_replaced_by_on_a_live_term_is_flagged(tmp_path, fixture_agents):
    g = _load(
        tmp_path,
        AREA
        + """
  - id: unmc:T
    pref_label: T
    definition: d
    in_subject_area: unmc:A
    replaced_by: unmc:U
    responsibilities:
      - {agent: 'unmc:role/OfficeA', governance_role: definition_owner}
    status: draft
  - id: unmc:U
    pref_label: U
    definition: d
    in_subject_area: unmc:A
    responsibilities:
      - {agent: 'unmc:role/OfficeA', governance_role: definition_owner}
    status: draft
""",
        fixture_agents,
    )
    assert any("Only a deprecated term is replaced" in str(p) for p in checks.check_governance(g))


def test_broader_cycle_is_flagged(tmp_path, fixture_agents):
    g = _load(
        tmp_path,
        AREA
        + """
  - id: unmc:T
    pref_label: T
    definition: d
    in_subject_area: unmc:A
    broader: [unmc:U]
    responsibilities:
      - {agent: 'unmc:role/OfficeA', governance_role: definition_owner}
    status: draft
  - id: unmc:U
    pref_label: U
    definition: d
    in_subject_area: unmc:A
    broader: [unmc:T]
    responsibilities:
      - {agent: 'unmc:role/OfficeA', governance_role: definition_owner}
    status: draft
""",
        fixture_agents,
    )
    assert any("own broader term" in str(p) for p in checks.check_governance(g))


def test_unused_agent_warns_but_does_not_fail(tmp_path, fixture_agents):
    g = _load(
        tmp_path,
        AREA
        + """
  - id: unmc:T
    pref_label: T
    definition: d
    in_subject_area: unmc:A
    responsibilities:
      - {agent: 'unmc:role/OfficeA', governance_role: definition_owner}
    status: draft
""",
        fixture_agents,
    )
    # OfficeB is registered but holds nothing yet -- a normal intermediate
    # state while a subject area is being set up, so it must not fail a build.
    assert checks.check_governance(g) == []
    assert any("holds no governance role yet" in str(p) for p in checks.warnings(g))


def test_missing_steward_warns_on_a_live_term(tmp_path, fixture_agents):
    g = _load(
        tmp_path,
        AREA
        + """
  - id: unmc:T
    pref_label: T
    definition: A real definition.
    definition_source: https://example.edu/s
    in_subject_area: unmc:A
    responsibilities:
      - {agent: 'unmc:role/OfficeA', governance_role: definition_owner}
    status: approved
""",
        fixture_agents,
    )
    assert checks.check_governance(g) == []
    assert any("no data_steward" in str(p) for p in checks.warnings(g))


TERM = """
  - id: unmc:T
    pref_label: T
    definition: d
    in_subject_area: unmc:A
    responsibilities:
      - {agent: 'unmc:role/OfficeB', governance_role: definition_owner}
    status: draft
"""


def test_office_contacts_resolve_to_people(glossary):
    # The fixture staffs Office B with Sam Rivera via `contacts`.
    office_b = glossary.agents["unmc:role/OfficeB"]
    assert [p.name for p in office_b.contacts] == ["Sam Rivera"]
    assert office_b.contacts[0].id in glossary.people


def test_dangling_contact_reference_fails(tmp_path):
    agents = tmp_path / "agents.yaml"
    agents.write_text(
        """
agents:
  - id: unmc:role/OfficeA
    pref_label: Office A
  - id: unmc:role/OfficeB
    pref_label: Office B
    contacts: [unmc:person/Ghost]
""",
        encoding="utf-8",
    )
    term = tmp_path / "case.yaml"
    term.write_text(AREA + TERM, encoding="utf-8")
    with pytest.raises(GlossaryError, match="unmc:person/Ghost"):
        load([term], agents, tmp_path)


def test_duplicate_person_fails(tmp_path):
    agents = tmp_path / "agents.yaml"
    agents.write_text(
        """
people:
  - {id: unmc:person/Jane, name: Jane Doe}
  - {id: unmc:person/Jane, name: Jane Roe}
agents:
  - id: unmc:role/OfficeA
    pref_label: Office A
  - id: unmc:role/OfficeB
    pref_label: Office B
""",
        encoding="utf-8",
    )
    term = tmp_path / "case.yaml"
    term.write_text(AREA + TERM, encoding="utf-8")
    with pytest.raises(GlossaryError, match="duplicate person"):
        load([term], agents, tmp_path)


def test_unstaffed_person_warns_but_does_not_fail(tmp_path):
    agents = tmp_path / "agents.yaml"
    agents.write_text(
        """
people:
  - {id: unmc:person/Jane, name: Jane Doe}
agents:
  - id: unmc:role/OfficeA
    pref_label: Office A
  - id: unmc:role/OfficeB
    pref_label: Office B
""",
        encoding="utf-8",
    )
    term = tmp_path / "case.yaml"
    term.write_text(AREA + TERM, encoding="utf-8")
    g = load([term], agents, tmp_path)
    assert checks.check_governance(g) == []
    assert any("staffs no office yet" in str(p) for p in checks.warnings(g))
