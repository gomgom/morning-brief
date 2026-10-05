#!/usr/bin/env python3
"""Check a rendered Morning Brief against the parts of the Verify list that code can check.

Usage:
    python3 scripts/verify_brief.py <brief.html>

Exits 0 when every check passes, 1 otherwise. Standard library only.
"""

import re
import sys
from html.parser import HTMLParser
from pathlib import Path

BUTTON_PREFIX = "https://chatgpt.com/?q="
FORBIDDEN_CLASSES = {"card", "badge", "chip", "pill", "tag", "footer", "timestamp"}
PROCESS_PHRASES = [
    "검증되지 않아",
    "확인하지 못",
    "찾지 못했",
    "생략했",
    "죄송",
    "wasn't able to",
    "couldn't find",
    "unable to verify",
    "surfacing this because",
    "you've got this",
]


class Page(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.meta = {}
        self.stack = []
        self.hrefs = []
        self.buttons = []
        self.sections = []
        self.acts = 0
        self.markers = 0
        self.terrain_paths = 0
        self.clay = 0
        self.order = []
        self.forbidden = []
        self.remote = []
        self.text = []
        self._button = None
        self._section = None

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        classes = set((a.get("class") or "").split())
        self.stack.append(tag)
        if tag == "meta" and a.get("name"):
            self.meta[a["name"]] = a.get("content", "")
        if tag in ("p", "h1") and "date" in classes:
            self.order.append("date")
        if tag == "h1":
            self.order.append("h1")
        if tag == "footer":
            self.forbidden.append("<footer>")
        self.forbidden += [f".{c}" for c in classes & FORBIDDEN_CLASSES]
        if tag == "path" and a.get("id") == "terrain-path":
            self.terrain_paths += 1
        if tag == "circle" and "marker" in classes:
            self.markers += 1
            if "data-x" not in a:
                self.forbidden.append("marker without data-x")
        if "clay" in classes:
            self.clay += 1
        if tag == "div" and "act" in classes:
            self.acts += 1
        if tag == "section":
            self._section = {"kind": a.get("data-section"), "heading": False, "body": False}
            self.sections.append(self._section)
        if self._section is not None:
            if tag == "h2":
                self._section["heading"] = True
            if tag in ("li", "p"):
                self._section["body"] = True
        if tag == "a":
            href = a.get("href", "")
            self.hrefs.append(href)
            if "button" in classes:
                self._button = {"href": href, "label": ""}
                self.buttons.append(self._button)
        if tag in ("script", "img", "iframe", "link", "source", "video", "audio"):
            src = a.get("src") or a.get("href") or ""
            if src:
                self.remote.append(f"<{tag}> {src}")

    def handle_endtag(self, tag):
        if self.stack:
            self.stack.pop()
        if tag == "a":
            self._button = None
        if tag == "section":
            self._section = None

    def handle_data(self, data):
        if self._button is not None:
            self._button["label"] += data
        if self.stack and self.stack[-1] not in ("style", "script"):
            self.text.append(data)


def check(source):
    page = Page()
    page.feed(source)
    errors, warnings = [], []
    mode = page.meta.get("mb-mode", "brief")
    buttons_on = page.meta.get("mb-buttons") == "on"

    if "__EMBEDDED_FONT_CSS__" in source:
        errors.append("font marker was not replaced")
    if not re.search(r"@font-face\s*\{", source):
        warnings.append("no embedded font; headline falls back to system serif")
    if re.search(r"url\(\s*['\"]?https?:", source, re.I):
        errors.append("CSS references a remote URL")
    if page.remote:
        errors.append("external resources: " + ", ".join(page.remote))

    for href in page.hrefs:
        if not href.startswith("https://"):
            errors.append(f"non-https link: {href[:80]}")
    if page.forbidden:
        errors.append("forbidden elements: " + ", ".join(sorted(set(page.forbidden))))

    if page.buttons and not buttons_on:
        errors.append("buttons rendered without the exact opt-in phrase")
    for b in page.buttons:
        if not b["href"].startswith(BUTTON_PREFIX):
            errors.append(f"button href must start with {BUTTON_PREFIX}")
        if len(b["label"].split()) > 5:
            errors.append(f'button label longer than 5 words: "{b["label"].strip()}"')

    if mode == "brief":
        if page.order[:2] != ["date", "h1"]:
            errors.append("the day-date line must sit directly above the headline")
        if page.terrain_paths != 1:
            errors.append("expected exactly one terrain path")
        if page.acts != 3:
            errors.append(f"expected three acts, found {page.acts}")
        if page.clay > 1:
            errors.append("clay used more than once in the drawing")
        if page.clay == 0 and not page.buttons:
            errors.append("no clay accent and no buttons")
        kinds = [s["kind"] for s in page.sections]
        core = [k for k in kinds if k != "extra"]
        if core not in (["attention", "resolved"], ["attention"], ["resolved"], ["calm"]):
            errors.append(f"core lists out of order: {core}")
        if "extra" in kinds and kinds.index("extra") < len(core):
            errors.append("requested sections must come after Resolved")
        for s in page.sections:
            if s["kind"] != "calm" and not (s["heading"] and s["body"]):
                errors.append("a section is missing its heading or content")

    visible = " ".join(page.text)
    for phrase in PROCESS_PHRASES:
        if phrase.lower() in visible.lower():
            warnings.append(f'voice: process or apology phrase "{phrase}"')
    return errors, warnings


def main():
    if len(sys.argv) != 2:
        print(__doc__.strip(), file=sys.stderr)
        return 2
    source = Path(sys.argv[1]).read_text(encoding="utf-8")
    errors, warnings = check(source)
    for w in warnings:
        print(f"WARNING: {w}")
    for e in errors:
        print(f"FAIL: {e}")
    if errors:
        return 1
    print("OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
