#!/usr/bin/env python3
"""Build the article lists for the site.

Reads every article file in site/philosophy/articles/ and
site/history/articles/, then writes the lists on:

  site/philosophy/index.html  (philosophy articles)
  site/history/index.html     (history articles)
  site/articles/index.html    (every article, both sections)

It also sorts loose files in site/catacombs/files/ into type folders
(pdfs, images, documents, and so on, with "other" for anything else) and
lists every file on site/catacombs/index.html, grouped by folder.

Last, it builds the plain version of the Catacombs: site/catacombs/plain.html
and site/catacombs/files.json (see plain.py).

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
import shutil
import urllib.parse
from pathlib import Path

from plain import build_plain

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


# ---------- THE CATACOMBS ----------

CATACOMBS = ROOT / "catacombs" / "files"

# Each folder in site/catacombs/files/, in the order it shows on the page,
# with its heading and the file extensions that belong in it.
# Anything that matches none of these goes in "other".
FOLDERS = [
    ("pdfs", "PDFs", {"pdf"}),
    ("images", "Images", {"png", "jpg", "jpeg", "gif", "webp", "svg", "bmp", "tif", "tiff", "heic", "ico"}),
    ("documents", "Documents", {"doc", "docx", "odt", "rtf", "pages", "epub"}),
    ("text", "Text Files", {"txt", "md", "markdown", "rst", "log", "tex"}),
    ("spreadsheets", "Spreadsheets", {"xls", "xlsx", "ods", "csv", "tsv", "numbers"}),
    ("slides", "Slides", {"ppt", "pptx", "odp", "key"}),
    ("audio", "Audio", {"mp3", "wav", "flac", "ogg", "m4a", "aac", "aiff", "mid", "midi"}),
    ("video", "Video", {"mp4", "mov", "webm", "mkv", "avi", "m4v"}),
    ("archives", "Archives", {"zip", "7z", "tar", "gz", "tgz", "rar", "bz2", "xz"}),
    ("fonts", "Fonts", {"otf", "ttf", "woff", "woff2"}),
    ("other", "Other Stuff", set()),
]
FOLDER_NAMES = {name: title for name, title, _ in FOLDERS}

# GitHub warns about files over 50 MB and refuses files over 100 MB
SIZE_WARNING = 50 * 1024 * 1024


def folder_for(path):
    ext = path.suffix.lower().lstrip(".")
    for name, _, exts in FOLDERS:
        if ext in exts:
            return name
    return "other"


def is_hidden(rel):
    """Hidden files, drafts, and folder placeholders start with . or _"""
    return any(part.startswith((".", "_")) for part in rel.parts)


def sort_catacombs():
    """Move loose files sitting directly in catacombs/files/ into their type folder.

    Files already inside a folder are left alone, so anything placed by hand
    stays where it was put. Returns the number of files moved.
    """
    if not CATACOMBS.is_dir():
        return 0

    for name, _, _ in FOLDERS:
        (CATACOMBS / name).mkdir(exist_ok=True)
        keep = CATACOMBS / name / ".gitkeep"
        if not keep.exists():
            keep.touch()

    moved = 0
    for p in sorted(CATACOMBS.iterdir()):
        if not p.is_file() or is_hidden(Path(p.name)):
            continue
        dest_dir = CATACOMBS / folder_for(p)
        dest = dest_dir / p.name
        # Never overwrite: add -1, -2, and so on if the name is taken
        n = 1
        while dest.exists():
            dest = dest_dir / f"{p.stem}-{n}{p.suffix}"
            n += 1
        p.rename(dest)
        print(f"sorted: {p.name} -> {dest.relative_to(CATACOMBS)}")
        moved += 1
    return moved


def human_size(n):
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024 or unit == "GB":
            return f"{n:.0f} {unit}" if unit == "B" else f"{n:.1f} {unit}"
        n /= 1024


def catacomb_groups():
    """Every Catacombs file, grouped by folder in display order.

    Returns a list of (folder, heading, [(path inside files/, size), ...]).
    """
    groups = {}
    if CATACOMBS.is_dir():
        for p in CATACOMBS.rglob("*"):
            rel = p.relative_to(CATACOMBS)
            if not p.is_file() or is_hidden(rel):
                continue
            size = p.stat().st_size
            if size > SIZE_WARNING:
                print(f"warning: {rel} is {human_size(size)}. GitHub refuses files over 100 MB.")
            # Loose files at the top level are listed under Other Stuff
            top = rel.parts[0] if len(rel.parts) > 1 else "other"
            groups.setdefault(top, []).append((rel, size))

    # Known folders first in their set order, then any custom folders A to Z
    order = [name for name, _, _ in FOLDERS if name in groups]
    order += sorted((g for g in groups if g not in FOLDER_NAMES), key=str.lower)
    return [
        (g,
         FOLDER_NAMES.get(g, g.replace("-", " ").replace("_", " ").title()),
         sorted(groups[g], key=lambda f: [part.lower() for part in f[0].parts]))
        for g in order
    ]


def file_li(rel, size, href_prefix, indent):
    """One <li> for a file: type tag, any inner folder, name, and size."""
    href = href_prefix + "/".join(urllib.parse.quote(part) for part in rel.parts)
    ext = rel.suffix.lstrip(".").upper() or "FILE"
    inner = rel.parts[1:-1] if len(rel.parts) > 1 else ()
    folder_txt = f'<span class="folder">{html.escape("/".join(inner))}/</span>' if inner else ""
    return (f'{indent}<li><span class="kind">{html.escape(ext)}</span>'
            f'{folder_txt}<a href="{html.escape(href, quote=True)}">{html.escape(rel.name)}</a>'
            f'<span class="size"><span class="num">{human_size(size)}</span></span></li>')


def catacomb_index(groups, indent):
    """The main Catacombs page: one link per category, each to its own page."""
    total = sum(len(files) for _, _, files in groups)
    if not total:
        return f'{indent}<p class="empty">Nothing buried here yet.</p>', 0
    lines = [f'{indent}<ul class="crypt-index">']
    for group, title, files in groups:
        href = urllib.parse.quote(group) + "/"
        lines.append(f'{indent}  <li><a href="{href}">{html.escape(title)}</a>'
                     f'<span class="count num">{len(files)}</span></li>')
    lines.append(f'{indent}</ul>')
    return "\n".join(lines), total


# Marker so the build can find and refresh only the pages it generated
CAT_MARKER = "<!-- auto-generated Catacombs category page -->"

_SUBPAGE = CAT_MARKER.join((
    "<!DOCTYPE html>\n",
    "\n<html lang=\"en\">\n"
    "<head>\n"
    "  <meta charset=\"UTF-8\">\n"
    "  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1.0\">\n"
    "  <title>{title_upper} | THE CATACOMBS | OWEN GRUMBLES</title>\n"
    "  <meta name=\"license\" content=\"Code: GPL-3.0. Writings: CC BY 4.0. Graphics and assets: All rights reserved.\">\n"
    "  <link rel=\"stylesheet\" href=\"../../style.css\">\n"
    "</head>\n"
    "<body>\n\n"
    "  <div class=\"hero\" role=\"img\" aria-label=\"Banner\"></div>\n\n"
    "  <div class=\"wrap\">\n\n"
    "    <header class=\"masthead\">\n"
    "      <img class=\"logo\" src=\"../../images/logo.png\" alt=\"Logo: Skeletal Wail with a Wooden Cross\">\n"
    "      <div class=\"title\">\n"
    "        <h1>Owen Grumbles</h1>\n"
    "      </div>\n"
    "    </header>\n\n"
    "    <nav>\n"
    "      <a href=\"../../philosophy/\">Philosophy</a>\n"
    "      <a href=\"../../history/\">History</a>\n"
    "      <a href=\"../../articles/\">All Articles</a>\n"
    "      <a href=\"../../catacombs/\">Catacombs</a>\n"
    "      <a href=\"../../#contact\">Contact</a>\n"
    "      <a href=\"../../#license\">License</a>\n"
    "    </nav>\n\n"
    "    <main class=\"content\">\n"
    "      <section id=\"catacombs\">\n"
    "        <a class=\"back\" href=\"../\">&larr; The Catacombs</a>\n"
    "        <h2>{title}</h2>\n"
    "        <div class=\"crypt\">\n"
    "{body}\n"
    "        </div>\n"
    "      </section>\n"
    "    </main>\n\n"
    "  </div>\n\n"
    "  <footer>\n"
    "    &copy; <span class=\"num\">2026</span> Owen Grumbles &bull; Code GPL-<span class=\"num\">3.0</span> &bull; Writings CC BY <span class=\"num\">4.0</span> &bull; Assets All Rights Reserved\n"
    "  </footer>\n\n"
    "</body>\n"
    "</html>\n",
))


def catacombs_subpage(title, body):
    return _SUBPAGE.format(title=html.escape(title), title_upper=html.escape(title.upper()), body=body)


def build_catacomb_pages(groups):
    """Write catacombs/<category>/index.html for each category that has files,
    and delete auto-generated pages for categories that no longer do."""
    cat_root = ROOT / "catacombs"
    current = {g for g, _, _ in groups}

    for d in sorted(cat_root.iterdir()):
        if d.is_dir() and d.name != "files":
            idx = d / "index.html"
            if idx.exists() and CAT_MARKER in idx.read_text(encoding="utf-8") and d.name not in current:
                shutil.rmtree(d)

    indent = " " * 10
    for group, title, files in groups:
        d = cat_root / group
        d.mkdir(exist_ok=True)
        lines = [f'{indent}<ul>']
        lines += [file_li(rel, size, "../files/", indent + "  ") for rel, size in files]
        lines.append(f'{indent}</ul>')
        (d / "index.html").write_text(catacombs_subpage(title, "\n".join(lines)), encoding="utf-8")
    return len(groups)


def main():
    indent = " " * 10

    moved = sort_catacombs()
    print(f"catacombs: sorted {moved} loose file(s)")
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

    groups = catacomb_groups()
    index_html, count = catacomb_index(groups, indent)
    fill(ROOT / "catacombs" / "index.html", "catacombs", index_html)
    pages = build_catacomb_pages(groups)
    print(f"catacombs: {count} file(s) across {pages} categor(ies)")

    build_plain(ROOT, groups, human_size)
    print("catacombs: plain version and files.json built")


if __name__ == "__main__":
    main()
