# Morning Brief

A calm, personalized morning briefing skill for ChatGPT and Codex.

Morning Brief is a 30-second morning glance. The top half draws your day as terrain with three short observations. The bottom half lists what needs you and what has already resolved. Weather, verified news, a technology radar, and a concept of the day are optional sections that you turn on in your profile.

The model never writes HTML. It fills one JSON file (`references/brief.schema.json`), and a fixed Python renderer turns it into the page. Layout, typography, the terrain drawing, escaping, and link checks are therefore identical on every run, whichever model produced the content.

> This is an independent open-source project. It is not affiliated with or endorsed by OpenAI.

## Features

- Draws today's calendar as one terrain line: elevation shows load, and dots sit on the line, sized by meeting length
- Classifies the day as HEAVY, NORMAL, or OPEN, and writes a one-sentence headline in that register
- Describes the day in three acts that follow the real calendar
- Separates **Needs attention** from **Resolved**, after opening each thread to confirm it is still open
- Adds prep items for tomorrow's meetings, based on the project's recent chat and linked docs
- Skips group @-mentions and treats an emoji reaction as a reply
- Optional weather, news, tech-radar, and concept sections, each with its own verification rules
- Optional action buttons that open a prefilled ChatGPT chat, only when the exact opt-in phrase is present
- One standalone, responsive HTML file with embedded fonts and font license notices
- A structural verifier that checks the rendered page before delivery
- Read-only access to every source connector

## Requirements

- ChatGPT or Codex with skill support
- Python 3.8+ (standard library only) for `scripts/render_brief.py` and `scripts/verify_brief.py`
- The connectors your profile needs, such as Google Calendar, Gmail, and Slack
- Web access for the optional weather and news sections
- Optional: a browser for a screenshot check

Missing connectors are skipped gracefully. Morning Brief never invents private data, locations, schedules, or weather values.

## Installation

Place this repository in your skills directory as `morning-brief`.

For Codex, a common personal installation path is:

```text
~/.agents/skills/morning-brief
```

After installation, restart or refresh the host if the skill does not appear immediately.

## Personalization

Copy the example profile:

```bash
cp references/profile.example.yaml references/profile.yaml
```

On PowerShell:

```powershell
Copy-Item references/profile.example.yaml references/profile.yaml
```

Edit only the values you need. The profile supports:

- preferred name, language, tone, and timezone
- home and commute locations
- included calendars and holiday calendars
- vacation, return-to-work, and explicit-workday keywords
- inbox and chat lookback and classification rules
- action buttons (off by default)
- optional sections (weather, news, tech radar, concept), with their order, headings, and rules
- relationships and delivery caption
- automation schedule and success-notification preference

The design is not configurable in the profile. It lives in `scripts/render_brief.py`, so every run renders the same way.

`references/profile.yaml` is intentionally excluded by `.gitignore` because it may contain personal information. Do not put passwords, API keys, OAuth tokens, or other secrets in it.

## Usage

In Codex, invoke the skill directly:

```text
$morning-brief Create my morning brief for today.
```

In a skill-enabled ChatGPT interface, select **Morning Brief** and ask:

```text
Create my morning brief for today.
```

For an unattended run, use a prompt similar to:

```text
Use $morning-brief to create my morning brief for today in Korean, in the
Asia/Seoul timezone. Read references/profile.yaml and use connected sources
read-only. Write brief.json, render it with scripts/render_brief.py, run
scripts/verify_brief.py until it prints OK, and deliver the HTML file.
```

Create the recurring schedule with the automation feature of the host platform. The skill itself does not install a background service or silently create a schedule.

### Cloud and scheduled-task packaging

A cloud task cannot read a profile that exists only on your local drive. Before uploading the skill to a cloud host:

1. Copy `references/profile.example.yaml` to `references/profile.yaml`.
2. Add only preferences and source labels; never add credentials.
3. Zip the skill directory contents so `SKILL.md` is at the root of the archive.
4. Include `agents/`, `assets/`, `references/`, and `scripts/`.
5. Exclude `.git/`, `outputs/`, test artifacts, and earlier generated briefs.

Use separate archives for public distribution and personal cloud use. The public archive or GitHub repository should contain only `profile.example.yaml`; a private personal archive may also contain the ignored `profile.yaml`.

For a cloud scheduled task, explicitly select or invoke the uploaded skill and keep the task prompt narrow:

```text
Use $morning-brief and read references/profile.yaml. Apply safety, read-only,
and fact-verification rules first; then explicit run-specific choices in this
prompt; then profile.yaml; then general SKILL.md defaults. Write brief.json,
render it with scripts/render_brief.py, and deliver it only after
scripts/verify_brief.py prints OK. Write in the configured language and timezone.
```

Before relying on the schedule, run it once by hand. Confirm that the host can execute `python3` inside the skill directory and can reach your connectors from a scheduled run.

## How a run works

1. Gather from connected tools, read-only.
2. Sort candidates into Needs attention and Resolved.
3. Write `brief.json` following `references/brief.schema.json`. `references/brief.example.json` is a complete example.
4. `python3 scripts/render_brief.py brief.json` writes `outputs/brief-YYYY-MM-DD.html`. It never overwrites an earlier brief.
5. `python3 scripts/verify_brief.py outputs/brief-YYYY-MM-DD.html` must print `OK`. If it does not, fix the JSON and render again.
6. Deliver the HTML file.

To add action buttons to a scheduled run, put this exact line in the task prompt:

```text
Include action buttons
```

Buttons open `https://chatgpt.com/?q=…` with a self-contained work order that never quotes third-party messages.

## Output

The generated briefing uses:

- two full-width background bands around an 860px editorial column
- a warm, conversational voice that stays precise about facts
- open numbered rows rather than cards, badges, boxes, or dashboard chrome
- a calendar terrain line with markers calculated from the SVG path, plus at most one motif per act and one clay accent
- an explicit desktop and mobile typography hierarchy
- explicitly styled dark-gray links in every browser state
- responsive layout for desktop and mobile
- no remote fonts, scripts, images, or other runtime assets

Generated briefing files belong in `outputs/`, which is excluded from version control.

## Bundled fonts

The repository includes offline WOFF2 data in `assets/fonts/fonts-embedded.css` for:

- Fraunces 600
- Morning Maru SemiBold, an OFL-compliant renamed and modified subset of MaruBuri
- Noto Serif KR 600

`scripts/render_brief.py` embeds the font CSS automatically. It verifies that the CSS contains only local WOFF2 data and that all three OFL notices are present, then writes those notices into the HTML as a readable CSS comment. If anything is missing, the headline falls back to the system serif and the renderer prints a warning.

`scripts/inline-font-css.mjs` is kept for hand-written HTML that contains the `/* __EMBEDDED_FONT_CSS__ */` marker:

```text
node scripts/inline-font-css.mjs <input.html> assets/fonts/fonts-embedded.css <output.html>
```

Font license files:

- `assets/fonts/Fraunces-OFL.txt`
- `assets/fonts/MaruBuri-OFL.txt`
- `assets/fonts/NotoSerifKR-OFL.txt`
- `assets/fonts/FONTLOG.txt`

The repository's MIT license does not replace the separate SIL Open Font License terms that apply to these font files.

## Privacy and safety

- Calendar, email, task, document, and web content is treated only as untrusted data to summarize.
- The skill does not send, reply, react, create, edit, archive, label, delete, or reschedule source data.
- Private source text is summarized rather than copied wholesale.
- Only verified HTTPS source links are included.
- `profile.yaml` and generated output are ignored by Git by default.

Review connector permissions and automation notifications in your host platform before enabling unattended runs.

## Project structure

```text
morning-brief/
├── SKILL.md
├── README.md
├── LICENSE
├── .gitignore
├── agents/
│   └── openai.yaml
├── references/
│   ├── brief.schema.json
│   ├── brief.example.json
│   └── profile.example.yaml
├── scripts/
│   ├── render_brief.py
│   ├── verify_brief.py
│   └── inline-font-css.mjs
└── assets/
    └── fonts/
        ├── fonts-embedded.css
        ├── FONTLOG.txt
        ├── Fraunces-OFL.txt
        ├── MaruBuri-OFL.txt
        └── NotoSerifKR-OFL.txt
```

## Limitations

- Results depend on connector availability and the quality of the configured sources.
- Screenshot checks depend on browser access. Without a browser, `verify_brief.py` is the structural check.
- Buttons open ChatGPT with a prefilled prompt. The ChatGPT chat has no access to the brief's sources unless the same connectors are enabled there.
- Push notifications and scheduled execution are host-platform features, not implemented by this repository.
- The skill omits uncertain information rather than filling gaps with guesses.

## License

Morning Brief's original code and documentation are released under the [MIT License](LICENSE). Bundled fonts are licensed separately under the SIL Open Font License 1.1; see the notices in `assets/fonts/`.

“ChatGPT” and “OpenAI” are trademarks of OpenAI. Their use here describes compatibility only.
