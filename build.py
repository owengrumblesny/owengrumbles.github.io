#!/usr/bin/env python3
"""Build the article lists for the site.

Reads every article file in site/philosophy/articles/ and
site/history/articles/, then writes the lists on:

  site/philosophy/index.html  (philosophy articles)
  site/history/index.html     (history articles)
  site/articles/index.html    (every article, both sections)

Each list sits between <!-- ARTICLES:START name --> and
<!-- ARTICLES:END --> markers, and only that part of the page is replaced.

The deploy workflow runs this before publishing. To preview locally, run:
  python3 build.py

Each article file should have:
  <title>Article Title | OWEN GRUMBLES</title>
  <meta name="date" content="YYYY-MM-DD">
  <meta name="description" content="One-sentence summary.">

Files whose names start with an underscore are treated as drafts and skipped.
"""

import datetime
import html
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent / "site"

SECTIONS = {
    "philosophy": "Philosophy",
    "history": "History",
}

TITLE_SUFFIX = re.compile(r"\s*\|\s*OWEN GRUMBLES\s*$", re.IGNORECASE)


def meta(text, name):
    """Return the content of <meta name="..."> from a page, or an empty string."""
    for tag in re.findall(r"<meta\b[^>]*>", text, re.IGNORECASE):
        if re.search(r'name\s*=\s*["\']' + re.escape(name) + r'["\']', tag, re.IGNORECASE):
            found = re.search(r'content\s*=\s*["\']([^"\']*)["\']', tag, re.IGNORECASE)
            if found:
                return html.unescape(found.group(1)).strip()
    return ""


def read_article(path, section):
    text = path.read_text(encoding="utf-8")

    title = ""
    found = re.search(r"<title>(.*?)</title>", text, re.IGNORECASE | re.DOTALL)
    if found:
        title = TITLE_SUFFIX.sub("", html.unescape(found.group(1)).strip())
    if not title:
        # Fall back to the file name, so a missing title never breaks the build
        title = path.stem.replace("-", " ").title()

    date = None
    raw_date = meta(text, "date")
    if raw_date:
        try:
            date = datetime.date.fromisoformat(raw_date)
        except ValueError:
            print(f"warning: {path.relative_to(ROOT)} has a date that is not YYYY-MM-DD: {raw_date!r}")

    # Write the visible date on the article page from its date meta tag,
    # so the date only has to be typed once
    if date:
        nice = date.strftime("%B %-d, %Y")
        new_text = re.sub(
            r'(<p class="date">).*?(</p>)',
            lambda m: m.group(1) + f'<span class="num">{nice}</span>' + m.group(2),
            text, count=1, flags=re.DOTALL,
        )
        if new_text != text:
            path.write_text(new_text, encoding="utf-8")

    return {
        "section": section,
        "file": path.name,
        "title": title,
        "date": date,
        "description": meta(text, "description"),
    }


def collect(section):
    folder = ROOT / section / "articles"
    if not folder.is_dir():
        return []
    articles = [
        read_article(p, section)
        for p in folder.glob("*.html")
        if not p.name.startswith("_")
    ]
    # Newest first; undated articles go last, in title order
    articles.sort(key=lambda a: (a["date"] is None, -(a["date"] or datetime.date.min).toordinal(), a["title"].lower()))
    return articles


def list_items(articles, href_prefix, show_tag, indent):
    if not articles:
        return f'{indent}<li class="empty">No articles yet.</li>'

    lines = []
    for a in articles:
        href = html.escape(href_prefix(a) + a["file"], quote=True)
        tag = f'<span class="tag">{SECTIONS[a["section"]]}</span>' if show_tag else ""
        parts = [f'{indent}<li>{tag}<a href="{href}">{html.escape(a["title"])}</a>']
        if a["date"]:
            nice = a["date"].strftime("%B %-d, %Y")
            parts.append(f'<span class="date"><span class="num">{nice}</span></span>')
        if a["description"]:
            parts.append(f'<p class="summary">{html.escape(a["description"])}</p>')
        parts.append("</li>")
        lines.append("".join(parts))
    return "\n".join(lines)


def fill(page, name, items_html):
    text = page.read_text(encoding="utf-8")
    pattern = re.compile(
        r"(<!-- ARTICLES:START " + re.escape(name) + r" -->\n)(.*?)(\n[ \t]*<!-- ARTICLES:END -->)",
        re.DOTALL,
    )
    new_text, count = pattern.subn(lambda m: m.group(1) + items_html + m.group(3), text)
    if count != 1:
        raise SystemExit(f"error: could not find the ARTICLES:START {name} marker in {page.relative_to(ROOT)}")
    page.write_text(new_text, encoding="utf-8")


def main():
    indent = " " * 10
    everything = []

    for section in SECTIONS:
        articles = collect(section)
        everything.extend(articles)
        fill(ROOT / section / "index.html", section,
             list_items(articles, lambda a: "articles/", False, indent))
        print(f"{section}: {len(articles)} article(s)")

    everything.sort(key=lambda a: (a["date"] is None, -(a["date"] or datetime.date.min).toordinal(), a["title"].lower()))
    fill(ROOT / "articles" / "index.html", "all",
         list_items(everything, lambda a: f"../{a['section']}/articles/", True, indent))
    print(f"all: {len(everything)} article(s)")


if __name__ == "__main__":
    main()
