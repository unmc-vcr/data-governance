"""Wrap `gen-doc` output in the site shell.

`gen-doc` documents the schema, not the terms: running it on terms.yaml
produces pages for Term, SubjectArea, each slot, and each enum, and the word
"Clinical Trial" appears nowhere in the output. That makes it the secondary,
technical half of the site -- useful to whoever maintains the schema, useless
to a steward looking up a definition.

Its output is Markdown with MkDocs-style relative links. Here it is rendered
to HTML and its .md links rewritten to .html so it works as a plain static
site, then dropped into the same shell as everything else.
"""

from __future__ import annotations

import re
import shutil
import subprocess
import tempfile
from pathlib import Path

from markdown_it import MarkdownIt

from .render import SCHEMA_DIR

# gen-doc emits one page per element. Sorted into these buckets for the rail.
_SECTION_ORDER = ["index", "TermSet", "Term", "SubjectArea", "Responsibility"]

# gen-doc targets MkDocs, so its output carries MkDocs-isms this site has to
# undo: a `search: boost:` front-matter block, and pretty-directory links of
# the form `../Term/` where this site serves flat `Term.html` files.
_FRONT_MATTER = re.compile(r"\A---\s*\n.*?\n---\s*\n", re.DOTALL)
_MERMAID_CLICK = re.compile(r'href\s+"\.\./([A-Za-z0-9_]+)/"')
# With --no-mergeimports, gen-doc links imported types by wrapping their full
# URI in its own relative-link pattern, producing `../http://.../`. Unwrap it.
_MERMAID_ABSOLUTE_CLICK = re.compile(r'href\s+"\.\./(https?://[^"]+?)/?"')


def generate(schema: Path, work_dir: Path) -> Path | None:
    """Run gen-doc into a temp directory. Returns the directory, or None."""
    out = work_dir / "gen-doc"
    out.mkdir(parents=True, exist_ok=True)
    result = subprocess.run(
        [
            "gen-doc",
            str(schema),
            "-d",
            str(out),
            "--no-mergeimports",
            "--index-name",
            "index",
        ],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return None
    if not any(out.glob("*.md")):
        return None
    return out


def _rewrite_links(html: str) -> str:
    """MkDocs-style `foo.md` links become `foo.html`."""

    def fix(match: re.Match) -> str:
        href = match.group(1)
        if href.startswith(("http://", "https://", "#", "mailto:")):
            return match.group(0)
        href = re.sub(r"\.md(#|$)", r".html\1", href)
        return f'href="{href}"'

    return re.sub(r'href="([^"]+)"', fix, html)


def _title_of(markdown: str, fallback: str) -> str:
    match = re.search(r"^#\s+(.+)$", markdown, re.MULTILINE)
    if not match:
        return fallback
    # gen-doc titles look like "Class: Term" or "Slot: pref_label".
    return re.sub(r"^(Class|Slot|Enum|Type|Subset):\s*", "", match.group(1).strip())


def _strip_first_heading(markdown: str) -> str:
    return re.sub(r"^#\s+.+\n", "", markdown, count=1)


def _clean_markdown(markdown: str) -> str:
    """Drop MkDocs front matter and point mermaid click targets at our files."""
    markdown = _FRONT_MATTER.sub("", markdown)
    markdown = _MERMAID_ABSOLUTE_CLICK.sub(r'href "\1"', markdown)
    return _MERMAID_CLICK.sub(r'href "\1.html"', markdown)


def _mermaid_blocks(html: str) -> tuple[str, bool]:
    """Convert fenced mermaid code blocks into nodes mermaid.js will render.

    The original source stays inside the element, so if the mermaid bundle is
    blocked or fails to load the reader sees the diagram source rather than an
    empty box.
    """
    found = False

    def replace(match: re.Match) -> str:
        nonlocal found
        found = True
        return f'<pre class="mermaid">{match.group(1)}</pre>'

    html = re.sub(
        r'<pre><code class="language-mermaid">(.*?)</code></pre>',
        replace,
        html,
        flags=re.DOTALL,
    )
    return html, found


def render_all(gen_doc_dir: Path, renderer) -> str | None:
    """Render every gen-doc page through the site shell.

    Returns the URL of the reference index, or None if there was nothing.
    """
    md = MarkdownIt("commonmark", {"typographer": True}).enable(["table", "strikethrough"])

    sources = sorted(gen_doc_dir.glob("*.md"))
    if not sources:
        return None

    entries = []
    for source in sources:
        text = _clean_markdown(source.read_text(encoding="utf-8"))
        stem = source.stem
        entries.append(
            {
                "stem": stem,
                "title": _title_of(text, stem),
                "markdown": text,
                "url": f"{SCHEMA_DIR}/{stem}.html",
            }
        )

    def sort_key(entry):
        try:
            return (0, _SECTION_ORDER.index(entry["stem"]))
        except ValueError:
            return (1, entry["title"].lower())

    entries.sort(key=sort_key)
    siblings = [{"label": e["title"], "url": e["url"]} for e in entries]

    for entry in entries:
        body = _rewrite_links(md.render(_strip_first_heading(entry["markdown"])))
        body, has_diagram = _mermaid_blocks(body)
        renderer.reference_page(
            entry["url"], entry["title"], body, siblings, has_diagram=has_diagram
        )

    # Copy any images or diagrams gen-doc produced alongside the markdown.
    for extra in gen_doc_dir.rglob("*"):
        if extra.is_file() and extra.suffix.lower() in {".png", ".svg", ".jpg", ".jpeg"}:
            target = renderer.out / SCHEMA_DIR / extra.relative_to(gen_doc_dir)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(extra, target)

    index = next((e for e in entries if e["stem"] == "index"), entries[0])
    return index["url"]


def build(schema: Path, renderer) -> str | None:
    with tempfile.TemporaryDirectory(prefix="unmc-gendoc-") as tmp:
        generated = generate(schema, Path(tmp))
        if generated is None:
            return None
        return render_all(generated, renderer)
