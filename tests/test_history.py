"""Per-term change history, derived by diffing definition files across commits.

The site shows a timeline per term, but git only tracks files. These tests
build a throwaway repository and check that file-level commits are correctly
attributed to individual terms.
"""

import subprocess
from pathlib import Path

import pytest

from glossary_site import history

TERM_A = """
subject_areas:
  - id: unmc:A
    pref_label: A
    definition: d
    responsibilities:
      - {agent: 'unmc:role/OfficeA', governance_role: definition_owner}
terms:
  - id: unmc:One
    pref_label: One
    definition: First definition.
    in_subject_area: unmc:A
    responsibilities:
      - {agent: 'unmc:role/OfficeA', governance_role: definition_owner}
    status: draft
"""

TERM_A_REWORDED = TERM_A.replace("First definition.", "Reworded definition.").replace(
    "status: draft", "status: in_review"
)

TERM_A_PLUS_B = TERM_A_REWORDED + """
  - id: unmc:Two
    pref_label: Two
    definition: Second term.
    in_subject_area: unmc:A
    responsibilities:
      - {agent: 'unmc:role/OfficeA', governance_role: definition_owner}
    status: draft
"""


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True)


@pytest.fixture
def repo(tmp_path):
    repo = tmp_path / "repo"
    (repo / "src" / "definitions").mkdir(parents=True)
    _git(repo.parent, "init", "-q", "repo")
    _git(repo, "config", "user.email", "tester@example.edu")
    _git(repo, "config", "user.name", "Test Author")

    path = repo / "src" / "definitions" / "alpha.yaml"

    path.write_text(TERM_A, encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "Add One")

    path.write_text(TERM_A_REWORDED, encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "Reword One and move to review")

    path.write_text(TERM_A_PLUS_B, encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "Add Two")

    return repo


def test_history_is_attributed_per_term(repo):
    paths = [repo / "src" / "definitions" / "alpha.yaml"]
    collected = history.collect(repo, paths)

    assert set(collected) == {"unmc:One", "unmc:Two"}

    # One was created, then changed. Two was only created.
    assert len(collected["unmc:One"]) == 2
    assert len(collected["unmc:Two"]) == 1


def test_history_is_newest_first_and_describes_the_change(repo):
    collected = history.collect(repo, [repo / "src" / "definitions" / "alpha.yaml"])
    one = collected["unmc:One"]

    assert one[0].iso >= one[1].iso
    assert "Status changed from Draft to In Review" in one[0].summary
    assert "Definition reworded" in one[0].summary
    # The commit subject is carried through so a good message still shows.
    assert "Reword One and move to review" in one[0].summary
    assert one[1].summary.startswith("Term created.")


def test_history_records_author_and_commit(repo):
    collected = history.collect(repo, [repo / "src" / "definitions" / "alpha.yaml"])
    change = collected["unmc:Two"][0]
    assert change.author == "Test Author"
    assert len(change.commit) == 8
    assert change.date  # formatted as "05 Feb 2024"


def test_adding_a_term_does_not_create_history_for_its_siblings(repo):
    """The third commit only added Two, so One gets no entry from it."""
    collected = history.collect(repo, [repo / "src" / "definitions" / "alpha.yaml"])
    subjects = [c.summary for c in collected["unmc:One"]]
    assert not any("Add Two" in s for s in subjects)


def test_history_does_not_leak_between_files_sharing_an_id(tmp_path):
    """Copying a term file and forgetting to change the id is a real mistake:
    for a few commits the same id lives in two files. History must stay scoped
    to each file, or the original term absorbs the copy's commits."""
    repo = tmp_path / "repo"
    terms = repo / "src" / "definitions" / "sp" / "terms"
    terms.mkdir(parents=True)
    _git(repo.parent, "init", "-q", "repo")
    _git(repo, "config", "user.email", "tester@example.edu")
    _git(repo, "config", "user.name", "Test Author")

    def term(term_id, label, status):
        return f"""
terms:
  - id: {term_id}
    pref_label: {label}
    definition: A definition.
    in_subject_area: unmc:A
    responsibilities:
      - {{agent: 'unmc:role/OfficeA', governance_role: definition_owner}}
    status: {status}
"""

    direct = terms / "direct_cost.yaml"
    indirect = terms / "indirect_cost.yaml"

    direct.write_text(term("unmc:DirectCost", "Direct Cost", "draft"), encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "Creates direct cost term")

    # Copied from direct_cost.yaml, id not yet corrected.
    indirect.write_text(term("unmc:DirectCost", "Indirect Cost", "draft"), encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "Creates indirect cost term")

    direct.write_text(term("unmc:DirectCost", "Direct Cost", "approved"), encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "Approve direct cost")

    indirect.write_text(term("unmc:IndirectCost", "Indirect Cost", "draft"), encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "Approve indirect cost")

    collected = history.collect(repo, [direct, indirect])

    direct_subjects = " ".join(c.summary for c in collected["unmc:DirectCost"])
    assert "indirect" not in direct_subjects.lower(), direct_subjects
    assert "Term removed" not in direct_subjects
    assert len(collected["unmc:DirectCost"]) == 2  # created, approved

    # The renamed term keeps the whole history of its own file -- and only its
    # own. git reports the copied file as C<score> and --follow traces into the
    # source's history; those commits belong to the source, not to this term.
    indirect_entries = collected["unmc:IndirectCost"]
    assert len(indirect_entries) == 2
    assert "Identifier changed from unmc:DirectCost to unmc:IndirectCost" in (
        indirect_entries[0].summary
    )
    assert indirect_entries[1].summary == "Term created. (Creates indirect cost term)"


def test_history_survives_a_file_rename(tmp_path):
    """Renaming a term's file must not reset its timeline."""
    repo = tmp_path / "repo"
    terms = repo / "src" / "definitions" / "cr" / "terms"
    terms.mkdir(parents=True)
    _git(repo.parent, "init", "-q", "repo")
    _git(repo, "config", "user.email", "tester@example.edu")
    _git(repo, "config", "user.name", "Test Author")

    typo = terms / "clincal_study.yaml"
    typo.write_text(TERM_A, encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "Creates clinical study term")

    fixed = terms / "clinical_study.yaml"
    _git(repo, "mv", str(typo.relative_to(repo)), str(fixed.relative_to(repo)))
    _git(repo, "commit", "-q", "-m", "Fixes typo in filename")

    collected = history.collect(repo, [fixed])
    assert any(c.summary.startswith("Term created.") for c in collected["unmc:One"])


def test_file_with_no_terms_at_an_earlier_commit(tmp_path):
    """A term file that started life empty (or holding only a subject area)
    must not crash the walk or emit a phantom entry."""
    repo = tmp_path / "repo"
    terms = repo / "src" / "definitions" / "cr" / "terms"
    terms.mkdir(parents=True)
    _git(repo.parent, "init", "-q", "repo")
    _git(repo, "config", "user.email", "tester@example.edu")
    _git(repo, "config", "user.name", "Test Author")

    path = terms / "later.yaml"
    path.write_text("# placeholder, no terms yet\n", encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "Placeholder")

    path.write_text(TERM_A, encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "Adds the term")

    collected = history.collect(repo, [path])
    assert [c.summary for c in collected["unmc:One"]] == [
        "Term created. (Adds the term)"
    ]


def test_missing_git_degrades_to_empty(tmp_path):
    """A non-repository must not break the build."""
    (tmp_path / "src" / "definitions").mkdir(parents=True)
    path = tmp_path / "src" / "definitions" / "alpha.yaml"
    path.write_text(TERM_A, encoding="utf-8")
    assert history.collect(tmp_path, [path]) == {}


def test_attach_sets_history_on_terms(repo, fixture_agents):
    from glossary_site.model import load

    paths = [repo / "src" / "definitions" / "alpha.yaml"]
    glossary = load(paths, fixture_agents, repo)
    history.attach(repo, paths, glossary)

    one = glossary.term_by_id("unmc:One")
    assert one.history
    assert one.last_changed == one.history[0].date
