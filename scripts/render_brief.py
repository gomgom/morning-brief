#!/usr/bin/env python3
"""Render a Morning Brief JSON file into one standalone HTML page.

Usage:
    python3 scripts/render_brief.py <brief.json> [--out <file.html>] [--font-css <css>]

The model writes only the JSON (see references/brief.schema.json). Layout, type,
colour, terrain geometry, escaping and link checks live here so every run looks
the same. Standard library only.
"""

import argparse
import datetime as dt
import html
import json
import math
import re
import sys
from pathlib import Path
from urllib.parse import quote, urlsplit

SKILL_DIR = Path(__file__).resolve().parent.parent
DEFAULT_FONT_CSS = SKILL_DIR / "assets" / "fonts" / "fonts-embedded.css"
REQUIRED_LICENSES = ["Fraunces-OFL.txt", "MaruBuri-OFL.txt", "NotoSerifKR-OFL.txt"]
FONT_MARKER = "/* __EMBEDDED_FONT_CSS__ */"

WIDTH, HEIGHT = 840, 170
BASELINE = 136
RISE = {"HEAVY": 100, "NORMAL": 66, "OPEN": 28}
FOCAL = (140, 420, 700)
BUTTON_ORIGIN = "https://chatgpt.com/"
RTL_LANGS = {"ar", "he", "fa", "ur", "yi", "ps", "sd", "ug"}
MOTIFS = {"sun", "half_sun", "moon", "birds", "fireworks", "flag", "ridge"}
DEFAULT_TEXT = {
    "ko": {
        "attention": "확인할 일",
        "resolved": "해결됨",
        "empty": "오늘 아침엔 챙길 게 없어요.",
    },
    "en": {
        "attention": "Needs attention",
        "resolved": "Resolved",
        "empty": "Nothing needs you this morning.",
    },
}


class BriefError(Exception):
    pass


WARNINGS = []


def warn(message):
    WARNINGS.append(message)


def esc(value):
    return html.escape(str(value), quote=True)


def safe_url(value):
    """Return the URL if it is a plain https URL, otherwise None."""
    if not isinstance(value, str) or not value.startswith("https://"):
        return None
    if re.search(r"[\s<>\"'`]", value):
        return None
    parts = urlsplit(value)
    if parts.scheme != "https" or not parts.netloc:
        return None
    return value


def linkify(text, links):
    """Escape text and wrap the first occurrence of each phrase in a link."""
    segments = [(str(text), None)]
    for phrase, url in links:
        url = safe_url(url)
        if not phrase or not url:
            continue
        for i, (chunk, linked) in enumerate(segments):
            if linked is None and phrase in chunk:
                before, after = chunk.split(phrase, 1)
                segments[i : i + 1] = [(before, None), (phrase, url), (after, None)]
                break
        else:
            warn(f'link phrase not found in text, left unlinked: "{phrase}"')
    out = []
    for chunk, url in segments:
        if not chunk:
            continue
        out.append(f'<a href="{esc(url)}">{esc(chunk)}</a>' if url else esc(chunk))
    return "".join(out)


def parse_time(value, field):
    match = re.fullmatch(r"(\d{1,2}):(\d{2})", str(value or ""))
    if not match:
        raise BriefError(f'{field}: expected "HH:MM", got {value!r}')
    hours, minutes = int(match.group(1)), int(match.group(2))
    if hours > 24 or minutes > 59 or (hours == 24 and minutes):
        raise BriefError(f"{field}: invalid time {value!r}")
    return hours * 60 + minutes


def word_count(text):
    return len(str(text).split())


# ---------------------------------------------------------------- calendar


def act_bounds(data):
    acts = data["acts"]
    if all("start" in a and "end" in a for a in acts):
        bounds = [parse_time(a["start"], f"acts[{i}].start") for i, a in enumerate(acts)]
        bounds.append(parse_time(acts[-1]["end"], "acts[2].end"))
    else:
        start = parse_time(data.get("day_start", "07:00"), "day_start")
        end = parse_time(data.get("day_end", "21:00"), "day_end")
        bounds = [start + (end - start) * i / 3 for i in range(4)]
    if any(b >= c for b, c in zip(bounds, bounds[1:])):
        raise BriefError("acts: start/end times must increase across the three acts")
    return bounds


def time_to_x(minutes, bounds):
    if minutes <= bounds[0]:
        return 0.0
    if minutes >= bounds[-1]:
        return float(WIDTH)
    third = WIDTH / 3
    for i in range(3):
        if minutes <= bounds[i + 1]:
            return i * third + (minutes - bounds[i]) / (bounds[i + 1] - bounds[i]) * third
    return float(WIDTH)


def load_events(data):
    events = []
    for i, ev in enumerate(data.get("events", [])):
        start = parse_time(ev.get("start"), f"events[{i}].start")
        end = parse_time(ev.get("end"), f"events[{i}].end")
        if end <= start:
            raise BriefError(f"events[{i}]: end must be after start")
        events.append(
            {
                "start": start,
                "end": end,
                "optional": bool(ev.get("optional")),
                "overlap": bool(ev.get("overlap")),
            }
        )
    return events


def classify(events):
    """HEAVY (>=5h in meetings or a 3+ cluster) / OPEN (<=1 short meeting) / NORMAL."""
    firm = sorted((e for e in events if not e["optional"]), key=lambda e: e["start"])
    if not firm:
        return "OPEN"
    busy, cluster, best_cluster = 0, 1, 1
    cur_start, cur_end = firm[0]["start"], firm[0]["end"]
    for prev, ev in zip(firm, firm[1:]):
        cluster = cluster + 1 if ev["start"] - prev["end"] <= 15 else 1
        best_cluster = max(best_cluster, cluster)
        if ev["start"] <= cur_end:
            cur_end = max(cur_end, ev["end"])
        else:
            busy += cur_end - cur_start
            cur_start, cur_end = ev["start"], ev["end"]
    busy += cur_end - cur_start
    if busy >= 300 or best_cluster >= 3:
        return "HEAVY"
    if len(firm) == 1 and firm[0]["end"] - firm[0]["start"] <= 60:
        return "OPEN"
    return "NORMAL"


def terrain_profile(events, bounds, day_class):
    step = 4
    xs = list(range(0, WIDTH + 1, step))
    load = [0.0] * len(xs)
    for ev in events:
        if ev["optional"]:
            continue
        x0, x1 = time_to_x(ev["start"], bounds), time_to_x(ev["end"], bounds)
        for i, x in enumerate(xs):
            if x0 <= x <= x1:
                load[i] += 1.0
    sigma = 16 / step
    radius = int(sigma * 3)
    kernel = [math.exp(-(k * k) / (2 * sigma * sigma)) for k in range(-radius, radius + 1)]
    smooth = []
    for i in range(len(xs)):
        total = weight = 0.0
        for k, w in enumerate(kernel):
            j = i + k - radius
            if 0 <= j < len(xs):
                total += load[j] * w
                weight += w
        smooth.append(total / weight)
    peak = max([1.0] + smooth)
    rise = RISE[day_class]
    ys = []
    for x, value in zip(xs, smooth):
        ripple = 1.6 * math.sin(x / 37.0) + 0.9 * math.sin(x / 13.0 + 1.3)
        ys.append(BASELINE - rise * value / peak + ripple)
    return xs, ys, smooth


def y_at(x, xs, ys):
    x = min(max(x, 0), WIDTH)
    i = min(int(x // (xs[1] - xs[0])), len(xs) - 2)
    t = (x - xs[i]) / (xs[i + 1] - xs[i])
    return ys[i] + (ys[i + 1] - ys[i]) * t


def smooth_path(points):
    """Catmull-Rom through the points, written as cubic Beziers."""
    d = [f"M{points[0][0]:.1f} {points[0][1]:.1f}"]
    for i in range(len(points) - 1):
        p0 = points[max(i - 1, 0)]
        p1, p2 = points[i], points[i + 1]
        p3 = points[min(i + 2, len(points) - 1)]
        c1 = (p1[0] + (p2[0] - p0[0]) / 6, p1[1] + (p2[1] - p0[1]) / 6)
        c2 = (p2[0] - (p3[0] - p1[0]) / 6, p2[1] - (p3[1] - p1[1]) / 6)
        d.append(
            f"C{c1[0]:.1f} {c1[1]:.1f} {c2[0]:.1f} {c2[1]:.1f} {p2[0]:.1f} {p2[1]:.1f}"
        )
    return " ".join(d)


def motif_svg(kind, x, cls, xs, ys):
    if kind == "sun":
        return f'<circle class="{cls}" cx="{x:.1f}" cy="34" r="10"></circle>'
    if kind == "half_sun":
        y = y_at(x, xs, ys)
        rays = "".join(
            f'<line x1="{12 * math.cos(a):.1f}" y1="{-12 * math.sin(a):.1f}" '
            f'x2="{18 * math.cos(a):.1f}" y2="{-18 * math.sin(a):.1f}"></line>'
            for a in (math.pi / 6, math.pi / 2, 5 * math.pi / 6)
        )
        return (
            f'<g class="{cls}" data-x="{x:.1f}" transform="translate({x:.1f} {y:.1f})">'
            f'<path d="M-9 0 A9 9 0 0 1 9 0"></path>{rays}</g>'
        )
    if kind == "moon":
        return (
            f'<path class="{cls}" transform="translate({x:.1f} 34)" '
            'd="M3 -11 A11 11 0 1 0 3 11 A8.5 8.5 0 1 1 3 -11 Z"></path>'
        )
    if kind == "birds":
        wing = "M-9 0 Q-4.5 -6 0 0 Q4.5 -6 9 0"
        return (
            f'<g class="{cls}"><path transform="translate({x - 14:.1f} 42)" d="{wing}"></path>'
            f'<path transform="translate({x + 12:.1f} 30)" d="M-7 0 Q-3.5 -5 0 0 Q3.5 -5 7 0"></path></g>'
        )
    if kind == "fireworks":
        rays = "".join(
            f'<line x1="{5 * math.cos(a):.1f}" y1="{5 * math.sin(a):.1f}" '
            f'x2="{12 * math.cos(a):.1f}" y2="{12 * math.sin(a):.1f}"></line>'
            for a in (k * math.pi / 4 for k in range(8))
        )
        return f'<g class="{cls}" transform="translate({x:.1f} 34)">{rays}</g>'
    if kind == "flag":
        y = y_at(x, xs, ys)
        return (
            f'<g class="{cls}" data-x="{x:.1f}" transform="translate({x:.1f} {y:.1f})">'
            '<line x1="0" y1="0" x2="0" y2="-26"></line>'
            '<path d="M0 -26 L13 -21.5 L0 -17"></path></g>'
        )
    raise BriefError(f"unknown motif kind {kind!r}")


def ridge_svg(xs, ys, cls):
    """A distant second ridge with a saddle, hidden wherever the main line rises past it."""
    paths, run = [], []
    for x, y in zip(xs[::2], ys[::2]):
        saddle = 14 * math.cos((x - WIDTH / 2) / WIDTH * 2 * math.pi)
        ridge = BASELINE - 58 - saddle + 3 * math.sin(x / 41.0)
        if ridge < y - 10:
            run.append((x, ridge))
        else:
            if len(run) > 3:
                paths.append(run)
            run = []
    if len(run) > 3:
        paths.append(run)
    return "".join(f'<path class="{cls}" d="{smooth_path(pts)}"></path>' for pts in paths)


def build_terrain(data, buttons_on):
    bounds = act_bounds(data)
    events = load_events(data)
    day_class = classify(events)
    given = data.get("day_class")
    if given and given != day_class:
        warn(f"day_class {given} differs from the calendar ({day_class}); using {day_class}")
    xs, ys, load = terrain_profile(events, bounds, day_class)
    points = [(x, y) for x, y in zip(xs, ys)][::3]
    if points[-1][0] != WIDTH:
        points.append((xs[-1], ys[-1]))
    parts = []

    motifs = [dict(m) for m in data.get("motifs", [])]
    seen_acts = set()
    for i, m in enumerate(motifs):
        if m.get("kind") not in MOTIFS:
            raise BriefError(f"motifs[{i}]: kind must be one of {sorted(MOTIFS)}")
        if m["kind"] == "ridge":
            if day_class != "HEAVY":
                raise BriefError("motifs: a second ridge is only for HEAVY days")
            continue
        act = m.get("act")
        if act not in (0, 1, 2):
            raise BriefError(f"motifs[{i}]: act must be 0, 1 or 2")
        if act in seen_acts:
            raise BriefError(f"motifs: at most one motif per act (act {act})")
        seen_acts.add(act)
    clay = [m for m in motifs if m.get("clay")]
    if len(clay) > 1:
        raise BriefError("motifs: clay is rationed to one accent across the drawing")
    if not clay and not buttons_on:
        sky = [m for m in motifs if m["kind"] != "ridge"]
        if sky:
            sky[0]["clay"] = True
        else:
            third = len(load) // 3
            quiet = min(range(3), key=lambda a: sum(load[a * third : (a + 1) * third]))
            if quiet in seen_acts:
                quiet = next(a for a in range(3) if a not in seen_acts)
            motifs.append({"kind": "sun", "act": quiet, "clay": True})
            warn(f"no clay accent and no buttons; added a clay sun over act {quiet}")

    for m in motifs:
        if m["kind"] == "ridge":
            parts.append(ridge_svg(xs, ys, "ridge"))
    parts.append(f'<path id="terrain-path" class="line" d="{smooth_path(points)}"></path>')

    markers = []
    for ev in events:
        if ev["end"] <= bounds[0] or ev["start"] >= bounds[-1]:
            warn("an event outside the three acts was not drawn")
            continue
        x = time_to_x((ev["start"] + ev["end"]) / 2, bounds)
        if ev["optional"]:
            r, cls = 6, "marker optional"
        else:
            r = 6 + 7 * min(1.0, (ev["end"] - ev["start"]) / 120)
            cls = "marker overlap" if ev["overlap"] else "marker"
        markers.append((r, x, cls))
    for r, x, cls in sorted(markers, key=lambda m: -m[0]):
        y = y_at(x, xs, ys)
        parts.append(
            f'<circle class="{cls}" data-x="{x:.1f}" cx="{x:.1f}" cy="{y:.1f}" r="{r:.1f}"></circle>'
        )
    for m in motifs:
        if m["kind"] == "ridge":
            continue
        cls = "motif clay" if m.get("clay") else "motif"
        parts.append(motif_svg(m["kind"], FOCAL[m["act"]], cls, xs, ys))
    return day_class, "\n".join(parts)


# ---------------------------------------------------------------- lists


def render_item(n, item, buttons_on, where):
    title = item.get("title")
    sentence = item.get("sentence")
    if not title or not sentence:
        raise BriefError(f"{where}: every item needs a title and a sentence")
    if where in ("attention", "resolved") and word_count(title) > 10:
        warn(f'{where}: title longer than 10 words: "{title}"')
    url = safe_url(item.get("url"))
    if item.get("url") and not url:
        warn(f"{where}: dropped a non-https link")
    title_html = f'<a href="{esc(url)}">{esc(title)}</a>' if url else esc(title)
    links = [(item.get("source_phrase"), url)] if url and item.get("source_phrase") else []
    links += [(l.get("phrase"), l.get("url")) for l in item.get("links", [])]
    out = [
        f'<li><span class="num">{n}</span><div>',
        f'<p class="item-title">{title_html}</p>',
        f'<p class="item-text">{linkify(sentence, links)}</p>',
    ]
    button = item.get("button")
    if button and not buttons_on:
        warn(f"{where}: button ignored because buttons are off")
    elif button:
        label, seed = button.get("label"), button.get("seed")
        if not label or not seed:
            raise BriefError(f"{where}: a button needs a label and a seed")
        href = BUTTON_ORIGIN + "?q=" + quote(seed, safe="")
        out.append(f'<p class="btn-row"><a class="button" href="{esc(href)}">{esc(label)}</a></p>')
    out.append("</div></li>")
    return "".join(out)


def render_list(items, buttons_on, where):
    rows = [render_item(i + 1, item, buttons_on, where) for i, item in enumerate(items)]
    return '<ol class="items">' + "".join(rows) + "</ol>"


def render_paragraph(p):
    if isinstance(p, str):
        return f"<p>{esc(p)}</p>"
    links = [(l.get("phrase"), l.get("url")) for l in p.get("links", [])]
    return f"<p>{linkify(p.get('text', ''), links)}</p>"


# ---------------------------------------------------------------- page


CSS = """
:root {
  --wash: #F9F9F7; --bg: #FCFCFB; --ink: #2E2C27; --ink-soft: #6B6A63;
  --grey: #B4B3A8; --hair: #E4E3DC; --edge: #E1E1DF; --clay: #C6613F; --clay-hover: #AE5133;
  --sans: -apple-system, BlinkMacSystemFont, "Segoe UI", "Apple SD Gothic Neo", "Malgun Gothic", "Noto Sans KR", sans-serif;
  --serif: "Fraunces", "Morning Maru", "Noto Serif KR", Georgia, serif;
}
* { box-sizing: border-box; }
html { -webkit-text-size-adjust: 100%; }
body { margin: 0; background: var(--bg); color: var(--ink); font-family: var(--sans); font-style: normal; -webkit-font-smoothing: antialiased; overflow-x: hidden; word-break: keep-all; overflow-wrap: break-word; }
.band { width: 100%; }
.top { background: var(--wash); border-bottom: 1px solid var(--edge); }
.bottom { background: var(--bg); }
.inner { max-width: 860px; margin: 0 auto; padding: 64px 40px 52px; }
.bottom .inner { padding: 56px 40px 80px; }
.date { margin: 0 0 14px; font-size: 13px; color: var(--ink-soft); letter-spacing: 0.02em; }
h1 { margin: 0; font-family: var(--serif); font-weight: 600; font-size: 40px; line-height: 1.36; letter-spacing: -0.01em; color: var(--ink); }
.page-message { margin: 0; font-size: 16px; line-height: 1.8; color: var(--ink-soft); }
.page-message + .page-message { margin-top: 8px; }
.terrain { display: block; width: 100%; height: auto; margin: 36px 0 10px; overflow: visible; }
.terrain .line { fill: none; stroke: var(--ink); stroke-width: 2; stroke-linecap: round; stroke-linejoin: round; }
.terrain .ridge { fill: none; stroke: var(--grey); stroke-width: 1.4; stroke-linecap: round; }
.terrain .motif, .terrain .motif * { fill: none; stroke: var(--ink-soft); stroke-width: 1.5; stroke-linecap: round; stroke-linejoin: round; }
.terrain .motif.clay, .terrain .motif.clay * { stroke: var(--clay); }
.terrain .marker { fill: var(--ink); }
.terrain .marker.optional { fill: var(--grey); }
.terrain .marker.overlap { fill: var(--bg); stroke: var(--ink); stroke-width: 1.6; }
.acts { display: grid; grid-template-columns: repeat(3, 1fr); }
.act { padding-inline: 22px; border-inline-start: 1px solid var(--hair); }
.act:first-child { padding-inline-start: 0; border-inline-start: 0; }
.act:last-child { padding-inline-end: 0; }
.act-range { margin: 0 0 6px; font-size: 12.5px; font-weight: 600; color: var(--ink); }
.act-text { margin: 0; font-size: 14px; line-height: 1.65; color: var(--ink-soft); }
.block + .block { margin-top: 52px; }
h2 { margin: 0 0 20px; font-family: var(--sans); font-size: 13px; font-weight: 600; letter-spacing: 0.10em; text-transform: uppercase; color: var(--ink); }
ol.items { list-style: none; margin: 0; padding: 0; }
ol.items li { display: grid; grid-template-columns: 22px 1fr; column-gap: 16px; }
ol.items li + li { margin-top: 22px; }
.num { font-size: 14px; line-height: 1.55; color: var(--grey); font-variant-numeric: tabular-nums; }
.item-title { margin: 0 0 4px; font-size: 15.5px; font-weight: 600; line-height: 1.5; color: var(--ink); }
.item-text { margin: 0; font-size: 14px; line-height: 1.7; color: var(--ink-soft); }
.prose p { margin: 0; font-size: 14.5px; line-height: 1.8; color: var(--ink-soft); }
.prose p + p { margin-top: 14px; }
.prose + ol.items { margin-top: 24px; }
.calm { margin: 0; font-size: 15.5px; line-height: 1.6; color: var(--ink-soft); }
.hint { margin: 28px 0 0; font-size: 14px; line-height: 1.7; color: var(--ink-soft); }
a, a:link, a:visited, a:hover, a:active { color: #3E3D38; text-decoration: underline; text-decoration-color: #AAA79C; text-decoration-thickness: 1px; text-underline-offset: 3px; }
.item-text a, .item-text a:link, .item-text a:visited, .item-text a:hover, .item-text a:active,
.prose a, .prose a:link, .prose a:visited, .prose a:hover, .prose a:active { color: var(--ink-soft); }
.btn-row { margin: 12px 0 0; }
a.button, a.button:link, a.button:visited { display: inline-block; background: var(--clay); border: 1px solid var(--clay); border-radius: 8px; padding: 9px 16px; font: 500 13px/1.2 var(--sans); color: #FCFCFB; text-decoration: none; }
a.button:hover, a.button:active { background: var(--clay-hover); border-color: var(--clay-hover); color: #FCFCFB; }
@media (max-width: 640px) {
  .inner { padding: 44px 22px 40px; }
  .bottom .inner { padding: 40px 22px 60px; }
  h1 { font-size: 30px; }
  .acts { grid-template-columns: 1fr; }
  .act, .act:first-child, .act:last-child { padding: 14px 0; border-inline-start: 0; border-top: 1px solid var(--hair); }
  .act:first-child { padding-top: 0; border-top: 0; }
}
"""

MARKER_JS = """
(function () {
  var path = document.getElementById("terrain-path");
  if (!path || !path.getTotalLength) return;
  var length = path.getTotalLength();
  function pointAtX(x) {
    var lo = 0, hi = length;
    for (var i = 0; i < 32; i++) {
      var mid = (lo + hi) / 2;
      if (path.getPointAtLength(mid).x < x) lo = mid; else hi = mid;
    }
    return path.getPointAtLength((lo + hi) / 2);
  }
  document.querySelectorAll("svg [data-x]").forEach(function (el) {
    var p = pointAtX(Number(el.getAttribute("data-x")));
    if (el.tagName.toLowerCase() === "circle") {
      el.setAttribute("cx", p.x.toFixed(2));
      el.setAttribute("cy", p.y.toFixed(2));
    } else {
      el.setAttribute("transform", "translate(" + p.x.toFixed(2) + " " + p.y.toFixed(2) + ")");
    }
  });
})();
"""


def font_block(font_css_path):
    """Return license notices plus font CSS, or a fallback comment with a warning."""
    try:
        css = font_css_path.read_text(encoding="utf-8").strip()
        if not re.search(r"@font-face\s*\{", css):
            raise BriefError("font CSS has no @font-face rule")
        if not re.search(r"data:font/woff2;base64,", css, re.I):
            raise BriefError("font CSS has no WOFF2 data URI")
        if re.search(r"https?://", css, re.I):
            raise BriefError("font CSS must not reference remote URLs")
        sections = []
        for name in REQUIRED_LICENSES:
            lic = font_css_path.parent / name
            if not lic.is_file():
                raise BriefError(f"required font license is missing: {name}")
            text = lic.read_text(encoding="utf-8").replace("*/", "* /").strip()
            sections.append(f"===== {name} =====\n{text}")
    except (OSError, BriefError) as exc:
        warn(f"fonts not embedded, using system serif fallback: {exc}")
        return "/* fonts unavailable: system serif fallback */"
    notices = "\n\n".join(sections)
    return f"/*\nBundled font license notices\n\n{notices}\n*/\n{css}"


def lang_text(data):
    lang = str(data.get("lang", "en")).lower()
    base = DEFAULT_TEXT.get(lang.split("-")[0], DEFAULT_TEXT["en"])
    labels = dict(base)
    labels.update(data.get("labels", {}))
    return lang, labels


def render(data, font_css_path):
    for field in ("date", "date_line"):
        if not data.get(field):
            raise BriefError(f"missing required field: {field}")
    lang, labels = lang_text(data)
    direction = "rtl" if lang.split("-")[0] in RTL_LANGS else "ltr"
    buttons_on = bool(data.get("buttons_enabled"))
    message = data.get("page_message")
    mode = "message" if message else "brief"

    top, bottom = [f'<p class="date">{esc(data["date_line"])}</p>'], []
    if message:
        if not isinstance(message, list) or not message:
            raise BriefError("page_message must be a list of sentences")
        top += [f'<p class="page-message">{esc(s)}</p>' for s in message]
    else:
        if not data.get("headline"):
            raise BriefError("missing required field: headline")
        acts = data.get("acts")
        if not isinstance(acts, list) or len(acts) != 3:
            raise BriefError("acts: exactly three acts are required")
        day_class, drawing = build_terrain(data, buttons_on)
        mirror = f' transform="translate({WIDTH} 0) scale(-1 1)"' if direction == "rtl" else ""
        top.append(f"<h1>{esc(data['headline'])}</h1>")
        top.append(
            f'<svg class="terrain" viewBox="0 0 {WIDTH} {HEIGHT}" role="img" '
            f'aria-label="{esc(day_class.lower())} day"><g{mirror}>{drawing}</g></svg>'
        )
        act_html = []
        for i, act in enumerate(acts):
            if not act.get("range") or not act.get("sentence"):
                raise BriefError(f"acts[{i}]: range and sentence are required")
            act_html.append(
                f'<div class="act"><p class="act-range">{esc(act["range"])}</p>'
                f'<p class="act-text">{esc(act["sentence"])}</p></div>'
            )
        top.append('<div class="acts">' + "".join(act_html) + "</div>")

        attention = data.get("attention", [])
        resolved = data.get("resolved", [])
        if attention:
            bottom.append(
                f'<section class="block" data-section="attention"><h2>{esc(labels["attention"])}</h2>'
                f'{render_list(attention, buttons_on, "attention")}</section>'
            )
        if resolved:
            bottom.append(
                f'<section class="block" data-section="resolved"><h2>{esc(labels["resolved"])}</h2>'
                f'{render_list(resolved, buttons_on, "resolved")}</section>'
            )
        if not attention and not resolved:
            empty = data.get("empty_line") or labels["empty"]
            bottom.append(
                f'<section class="block" data-section="calm"><p class="calm">{esc(empty)}</p></section>'
            )
        if data.get("connect_hint"):
            bottom[-1] = bottom[-1].replace(
                "</section>", f'<p class="hint">{esc(data["connect_hint"])}</p></section>', 1
            )
        for i, sec in enumerate(data.get("sections", [])):
            items, paragraphs = sec.get("items") or [], sec.get("paragraphs") or []
            if not sec.get("heading"):
                raise BriefError(f"sections[{i}]: heading is required")
            if not items and not paragraphs:
                warn(f'section "{sec["heading"]}" is empty and was dropped')
                continue
            body = ""
            if paragraphs:
                body += '<div class="prose">' + "".join(render_paragraph(p) for p in paragraphs) + "</div>"
            if items:
                body += render_list(items, buttons_on, f"sections[{i}]")
            bottom.append(
                f'<section class="block" data-section="extra"><h2>{esc(sec["heading"])}</h2>{body}</section>'
            )

    style = FONT_MARKER + "\n" + CSS
    page = [
        "<!doctype html>",
        f'<html lang="{esc(lang)}" dir="{direction}">',
        "<head>",
        '<meta charset="utf-8">',
        '<meta name="viewport" content="width=device-width, initial-scale=1">',
        f'<meta name="mb-mode" content="{mode}">',
        f'<meta name="mb-buttons" content="{"on" if buttons_on else "off"}">',
        f"<title>{esc(data['date_line'])}</title>",
        f"<style>{style}</style>",
        "</head>",
        "<body>",
        '<header class="band top"><div class="inner">' + "\n".join(top) + "</div></header>",
    ]
    if bottom:
        page.append('<main class="band bottom"><div class="inner">' + "\n".join(bottom) + "</div></main>")
    if mode == "brief":
        page.append(f"<script>{MARKER_JS}</script>")
    page += ["</body>", "</html>", ""]
    return "\n".join(page).replace(FONT_MARKER, font_block(font_css_path), 1)


def output_path(data, out):
    if out:
        path = Path(out)
        if path.exists():
            raise BriefError(f"refusing to overwrite an earlier brief: {path}")
        return path
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", str(data["date"])):
        raise BriefError('date: expected "YYYY-MM-DD"')
    folder = Path.cwd() / "outputs"
    now = dt.datetime.now()
    for suffix in ("", now.strftime("-%H%M"), now.strftime("-%H%M%S")):
        path = folder / f"brief-{data['date']}{suffix}.html"
        if not path.exists():
            return path
    raise BriefError("could not find a free output file name")


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("brief", help="brief JSON file")
    parser.add_argument("--out", help="output HTML path (never overwritten)")
    parser.add_argument("--font-css", default=str(DEFAULT_FONT_CSS), help="embedded font CSS")
    args = parser.parse_args()
    try:
        data = json.loads(Path(args.brief).read_text(encoding="utf-8"))
        page = render(data, Path(args.font_css))
        path = output_path(data, args.out)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(page, encoding="utf-8")
    except (OSError, ValueError, BriefError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    for message in WARNINGS:
        print(f"WARNING: {message}", file=sys.stderr)
    print(path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
