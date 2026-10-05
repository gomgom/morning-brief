#!/usr/bin/env python3
"""Package the skill as a zip with SKILL.md at the archive root.

Usage:
    python3 scripts/package_skill.py [--with-profile] [--out dist/morning-brief.zip]

By default the personal references/profile.yaml is left out, so the zip is safe
to share. Pass --with-profile only for your own private upload.
"""

import argparse
import sys
import zipfile
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parent.parent
INCLUDE = ["SKILL.md", "LICENSE", "README.md", "agents", "assets", "references", "scripts"]
SKIP_PARTS = {"__pycache__", ".git", "outputs", "dist"}
PROFILE = Path("references") / "profile.yaml"


def files(with_profile):
    for name in INCLUDE:
        path = SKILL_DIR / name
        candidates = [path] if path.is_file() else sorted(p for p in path.rglob("*") if p.is_file())
        for file in candidates:
            rel = file.relative_to(SKILL_DIR)
            if SKIP_PARTS & set(rel.parts) or file.suffix == ".pyc":
                continue
            if rel == PROFILE and not with_profile:
                continue
            yield file, rel


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--with-profile", action="store_true", help="include references/profile.yaml")
    parser.add_argument("--out", default=str(SKILL_DIR / "dist" / "morning-brief.zip"))
    args = parser.parse_args()

    if args.with_profile and not (SKILL_DIR / PROFILE).is_file():
        print("ERROR: references/profile.yaml does not exist", file=sys.stderr)
        return 1
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as archive:
        for file, rel in files(args.with_profile):
            archive.write(file, rel.as_posix())
    print(out)
    if args.with_profile:
        print("WARNING: this zip contains your personal profile.yaml; do not share it.", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
