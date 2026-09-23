"""Check that every internal link in the built site resolves to a real file.

    python -m terms_site.linkcheck site

Every page computes its own relative path back to the site root so that the
site works both under a GitHub Pages project subpath and from file:// when a
steward opens the PR-preview artifact out of the downloaded zip. That scheme
is easy to get subtly wrong -- one page at the wrong depth and a whole
section 404s -- and a broken link on a governance site costs trust. So CI
checks it.

External links are not fetched; this only verifies the site is internally
consistent.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import unquote, urldefrag

LINK = re.compile(r'(?:href|src)="([^"]+)"', re.IGNORECASE)

# "#" is deliberately absent: a same-page anchor still has to point at an id
# that exists, and that check happens below.
SKIP_PREFIXES = ("http://", "https://", "mailto:", "tel:", "data:", "//")


def check(root: Path) -> list[str]:
    problems: list[str] = []
    pages = sorted(root.rglob("*.html"))
    if not pages:
        return [f"{root}: no HTML pages found"]

    for page in pages:
        html = page.read_text(encoding="utf-8")
        anchors = {m.group(1) for m in re.finditer(r'id="([^"]+)"', html)}

        for raw in LINK.findall(html):
            if raw.startswith(SKIP_PREFIXES) or not raw.strip():
                continue

            target, fragment = urldefrag(raw)
            # Static assets carry a ?v=<digest> cache buster; the file on disk
            # is the part before the query.
            target = target.split("?", 1)[0]
            if not target:
                # Same-page anchor.
                if fragment and fragment not in anchors:
                    problems.append(
                        f"{page.relative_to(root)}: #{fragment} does not exist on this page"
                    )
                continue

            # 404.html uses root-absolute paths because it is served in
            # response to any URL, at any depth. Those resolve against the site
            # root, not the page's directory.
            path = unquote(target)
            base = root if path.startswith("/") else page.parent
            resolved = (base / path.lstrip("/")).resolve()
            if not resolved.exists():
                problems.append(
                    f"{page.relative_to(root)}: {raw} -> missing {_display(resolved, root)}"
                )
                continue

            # Guard against a relative path climbing out of the site.
            try:
                resolved.relative_to(root.resolve())
            except ValueError:
                problems.append(
                    f"{page.relative_to(root)}: {raw} escapes the site root"
                )

    return problems


def _display(path: Path, root: Path) -> str:
    try:
        return str(path.relative_to(root.resolve()))
    except ValueError:
        return str(path)


def main(argv: list[str] | None = None) -> int:
    args = argv if argv is not None else sys.argv[1:]
    root = Path(args[0]) if args else Path("site")
    if not root.exists():
        print(f"{root} does not exist; build the site first", file=sys.stderr)
        return 1

    problems = check(root)
    if problems:
        print(f"\n{len(problems)} broken internal link(s):", file=sys.stderr)
        for problem in problems:
            print(f"  - {problem}", file=sys.stderr)
        return 1

    pages = len(list(root.rglob("*.html")))
    print(f"All internal links resolve across {pages} page(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
