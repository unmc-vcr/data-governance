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
