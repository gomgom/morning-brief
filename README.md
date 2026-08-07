# Morning Brief

A calm, personalized morning briefing skill for ChatGPT and Codex.

Morning Brief turns connected calendar and inbox context, local weather, verified news, a technology radar, and one approachable concept into a single polished HTML briefing. The opening stays easy to scan, while the news, technology analysis, and concept sections provide enough depth to be useful.

> This is an independent open-source project. It is not affiliated with or endorsed by OpenAI.

## Features

- Summarizes the shape of today from connected calendars
- Writes a one-sentence editorial headline about the character of the day
- Describes the schedule in three natural, narrative time windows
- Separates items that need attention from recently resolved matters
- Explains each attention or resolved item with its date, status, deadline, and relevance
- Supports archived and inbox email searches
- Uses configurable locations and authoritative weather sources
- Groups verified news into five configurable categories with up to two items each
- Synthesizes two or three connected technology currents instead of listing article summaries
- Explains one approachable concept from analogy through mechanism, practical meaning, and limitations
- Produces one responsive, standalone HTML file
- Bundles its fonts and font license notices into the generated HTML
- Keeps all source connectors read-only while creating a brief
- Supports unattended recurring runs when the host platform provides automations

## Requirements

- ChatGPT or Codex with skill support
- The connectors needed by your profile, such as Google Calendar and Gmail
- Web access for current weather and news
- Node.js only when using the bundled font-inlining script
- A browser for the recommended visual verification step

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
- inbox lookback and classification rules
- preferred weather and air-quality sources
- news categories and item counts
- editorial voice, headline style, narrative schedule observations, and list depth
- technology-radar flows and concept-of-the-day depth
- exact layout, type scale, numbered-list treatment, and terrain decoration
- section order, relationships, and delivery caption
- automation schedule and success-notification preference

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
Use $morning-brief to create my morning brief for today in my configured
timezone. Read references/profile.yaml, use connected sources read-only,
save one standalone HTML file, visually verify it when possible, and notify
me after a successful delivery.
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
prompt; then profile.yaml; then general SKILL.md defaults. Create one verified
standalone HTML brief in the configured language and timezone.
```

## Output

The generated briefing uses:

- two full-width background bands around an 860px editorial column
- a warm, conversational voice that stays precise about facts
- open numbered rows rather than cards, badges, boxes, or dashboard chrome
- a calendar terrain line with markers calculated from the SVG path
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

Run the inlining helper after creating an HTML file containing the marker `/* __EMBEDDED_FONT_CSS__ */`:

```text
node scripts/inline-font-css.mjs <input.html> assets/fonts/fonts-embedded.css <output.html>
```

The helper verifies the font CSS and embeds the complete bundled OFL notices into the standalone HTML as a readable CSS comment.

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
│   └── profile.example.yaml
├── scripts/
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
- Visual verification depends on browser access in the execution environment.
- Push notifications and scheduled execution are host-platform features, not implemented by this repository.
- The skill omits uncertain information rather than filling gaps with guesses.

## License

Morning Brief's original code and documentation are released under the [MIT License](LICENSE). Bundled fonts are licensed separately under the SIL Open Font License 1.1; see the notices in `assets/fonts/`.

“ChatGPT” and “OpenAI” are trademarks of OpenAI. Their use here describes compatibility only.
