"""The relative-URL scheme is easy to get subtly wrong, so it is checked."""

from pathlib import Path

from glossary_site import build as build_module
from glossary_site import linkcheck

FIXTURES = Path(__file__).parent / "fixtures"
REPO_ROOT = Path(__file__).resolve().parents[1]


def _build(out: Path) -> Path:
    assert (
        build_module.build(
            schema=REPO_ROOT / "src" / "schema" / "glossary.yaml",
            definitions_dir=FIXTURES / "definitions",
            agents=FIXTURES / "agents.yaml",
            content_dir=FIXTURES / "content",
            out=out,
            skip_reference=True,
            repo_root=FIXTURES,
        )
        == 0
    )
    return out


def test_built_site_has_no_broken_links(tmp_path):
    site = _build(tmp_path / "site")
    assert linkcheck.check(site) == []


def test_broken_link_is_detected(tmp_path):
    site = _build(tmp_path / "site")
    page = site / "glossary.html"
    page.write_text(
        page.read_text(encoding="utf-8").replace(
            'href="terms/fully-loaded.html"', 'href="terms/gone.html"', 1
        ),
        encoding="utf-8",
    )
    problems = linkcheck.check(site)
    assert any("terms/gone.html" in p for p in problems)


def test_broken_same_page_anchor_is_detected(tmp_path):
    site = _build(tmp_path / "site")
    page = site / "guide.html"
    page.write_text(
        page.read_text(encoding="utf-8").replace(
            'href="#first-section"', 'href="#nowhere"', 1
        ),
        encoding="utf-8",
    )
    problems = linkcheck.check(site)
    assert any("#nowhere" in p for p in problems)


def test_external_and_mailto_links_are_skipped(tmp_path):
    site = _build(tmp_path / "site")
    page = site / "index.html"
    page.write_text(
        page.read_text(encoding="utf-8").replace(
            "</body>",
            '<a href="https://example.org/nope">x</a>'
            '<a href="mailto:nobody@example.org">y</a></body>',
            1,
        ),
        encoding="utf-8",
    )
    assert linkcheck.check(site) == []


def test_main_returns_nonzero_on_a_missing_directory(tmp_path):
    assert linkcheck.main([str(tmp_path / "does-not-exist")]) == 1
