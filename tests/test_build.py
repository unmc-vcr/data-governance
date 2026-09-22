"""End-to-end build, plus the content loader."""

import json
from pathlib import Path

import pytest

from glossary_site import build as build_module
from glossary_site import content

FIXTURES = Path(__file__).parent / "fixtures"
REPO_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def built(tmp_path_factory):
    out = tmp_path_factory.mktemp("site")
    code = build_module.build(
        schema=REPO_ROOT / "src" / "schema" / "glossary.yaml",
        definitions_dir=FIXTURES / "definitions",
        agents=FIXTURES / "agents.yaml",
        content_dir=FIXTURES / "content",
        out=out,
        skip_reference=True,
        repo_root=FIXTURES,
    )
    assert code == 0
    return out


def test_expected_pages_exist(built):
    for path in [
        "index.html",
        "glossary.html",
        "search.html",
        "how-to-read-a-term.html",
        "guide.html",
        "areas/alpha.html",
        "areas/beta.html",
        "terms/fully-loaded.html",
        "terms/beta-term.html",
        "terms/old-thing.html",
        "assets/site.css",
        "assets/site.js",
        "assets/search-index.json",
    ]:
        assert (built / path).exists(), f"missing {path}"


def test_term_page_renders_every_section(built):
    html = (built / "terms" / "fully-loaded.html").read_text(encoding="utf-8")
    assert "Fully Loaded" in html
    assert "AL.FUL.001" in html
    assert "Rules &amp; qualifiers" in html
    assert "Test System" in html
    assert "FULL_ID" in html
    assert "Monthly Test Summary" in html
    assert "Same as" in html and "Similar to" in html
    assert "ra:Study.identifier" in html
    assert "badge--sensitive" in html
    assert "Encrypted only" in html  # handling matrix
    assert "https://w3id.org/unmc/glossary/FullyLoaded" in html  # permanent link
    assert "Office A" in html and "Office B" in html
    assert "Ask for Sam Rivera" in html  # contact_name on Office B


def test_sections_are_omitted_when_there_is_no_data(built):
    html = (built / "terms" / "beta-term.html").read_text(encoding="utf-8")
    assert "Rules &amp; qualifiers" not in html
    assert "Source of record" not in html
    assert "Where it is used" not in html
    # But classification is present, so the handling panel is.
    assert "Handling at a glance" in html


def test_deprecated_term_points_at_its_replacement(built):
    html = (built / "terms" / "old-thing.html").read_text(encoding="utf-8")
    assert "badge--deprecated" in html
    assert "fully-loaded.html" in html
    assert "Use <a" in html


def test_glossary_rows_carry_filter_attributes(built):
    html = (built / "glossary.html").read_text(encoding="utf-8")
    assert 'data-area="alpha"' in html
    assert 'data-area="beta"' in html
    assert 'data-status="deprecated"' in html
    assert 'data-status="in_review"' in html
    assert 'data-filter="area:alpha"' in html


def test_relative_paths_are_depth_correct(built):
    term = (built / "terms" / "fully-loaded.html").read_text(encoding="utf-8")
    root = (built / "index.html").read_text(encoding="utf-8")
    assert 'href="../assets/site.css"' in term
    assert 'href="assets/site.css"' in root
    assert 'href="../glossary.html"' in term


def test_search_index_contents(built):
    entries = json.loads((built / "assets" / "search-index.json").read_text(encoding="utf-8"))
    kinds = {e["kind"] for e in entries}
    assert kinds == {"term", "area", "page"}

    loaded = next(e for e in entries if e["title"] == "Fully Loaded")
    assert "Kitchen Sink" in loaded["alt"]
    assert loaded["url"] == "terms/fully-loaded.html"
    assert "Office B" in loaded["meta"]

    assert any(e["title"] == "Fixture Guide" for e in entries)
    assert any(e["title"] == "Alpha Area" for e in entries)


def test_how_to_read_is_generated_from_the_schema(built):
    html = (built / "how-to-read-a-term.html").read_text(encoding="utf-8")
    # Slot descriptions come straight out of glossary.yaml.
    assert "Office, group, or role IRI" in html or "Other names people actually use" in html
    assert "Accountable for approving the definition" in html
    assert "Signed off. Reports may cite it." in html


def test_hub_counts_come_from_the_data(built):
    html = (built / "index.html").read_text(encoding="utf-8")
    assert "Approved terms in the dictionary" in html
    assert "Test Hub" in html


def test_nav_includes_authored_and_generated_groups(built):
    html = (built / "glossary.html").read_text(encoding="utf-8")
    assert "Fixture guide" in html
    assert "Alpha Area" in html
    assert "How to read a term" in html


def test_build_fails_on_a_dangling_reference(tmp_path):
    definitions = tmp_path / "definitions"
    definitions.mkdir()
    (definitions / "bad.yaml").write_text(
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
    broader: [unmc:Nope]
    responsibilities:
      - {agent: 'unmc:role/OfficeA', governance_role: definition_owner}
    status: draft
""",
        encoding="utf-8",
    )
    code = build_module.build(
        schema=REPO_ROOT / "src" / "schema" / "glossary.yaml",
        definitions_dir=definitions,
        agents=FIXTURES / "agents.yaml",
        content_dir=FIXTURES / "content",
        out=tmp_path / "out",
        skip_reference=True,
        repo_root=tmp_path,
    )
    assert code == 1


# ---------- content loader ----------


def test_content_requires_front_matter(tmp_path):
    (tmp_path / "x.md").write_text("# no front matter\n", encoding="utf-8")
    with pytest.raises(content.ContentError, match="front matter"):
        content.load(tmp_path)


def test_content_requires_a_title(tmp_path):
    (tmp_path / "x.md").write_text("---\neyebrow: hi\n---\nbody\n", encoding="utf-8")
    with pytest.raises(content.ContentError, match="no `title`"):
        content.load(tmp_path)


def test_only_one_hub_allowed(tmp_path):
    (tmp_path / "a.md").write_text("---\ntitle: A\nhub: true\n---\n", encoding="utf-8")
    (tmp_path / "b.md").write_text("---\ntitle: B\nhub: true\n---\n", encoding="utf-8")
    with pytest.raises(content.ContentError, match="more than one page"):
        content.load(tmp_path)


def test_callouts_and_toc(tmp_path):
    (tmp_path / "a.md").write_text(
        "---\ntitle: A\ntoc: true\n---\n\n## First\n\n> **Required**\n> Do the thing.\n\n## Second\n",
        encoding="utf-8",
    )
    pages = content.load(tmp_path)
    page = pages[0]
    assert 'class="callout callout--required"' in page.html
    assert "Do the thing." in page.html
    assert [entry["id"] for entry in page.toc] == ["first", "second"]
    assert '<h2 id="first"' in page.html


def test_nested_content_keeps_its_path(tmp_path):
    (tmp_path / "standards").mkdir()
    (tmp_path / "standards" / "x.md").write_text("---\ntitle: X\n---\nbody\n", encoding="utf-8")
    pages = content.load(tmp_path)
    assert pages[0].url == "standards/x.html"
