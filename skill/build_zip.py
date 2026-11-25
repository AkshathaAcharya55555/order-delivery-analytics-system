#!/usr/bin/env python3
"""
Validate and package the skill for upload to a skills marketplace.

    python skill/build_zip.py            -> skill/dist/order-delivery-analytics.zip

Checks the published packaging rules before zipping:
  * exactly one top-level folder, SKILL.md at its root
  * frontmatter has only name + description; name == folder name, slug format
  * description is non-empty; body is non-empty
  * text files only (no binaries), no symlinks, no OS junk / caches
  * no obvious hardcoded secrets
"""

import os
import re
import stat
import sys
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL = "order-delivery-analytics"
SRC = os.path.join(HERE, SKILL)
DIST = os.path.join(HERE, "dist")
TEXT_EXT = {".md", ".py", ".sql", ".json", ".yml", ".yaml", ".txt"}
SKIP_DIRS = {"__pycache__", ".pytest_cache"}
SKIP_FILES = {".DS_Store", "Thumbs.db"}
SECRET_PATTERNS = [r"AKIA[0-9A-Z]{16}", r"sk-[A-Za-z0-9]{20,}", r"ghp_[A-Za-z0-9]{30,}",
                   r"postgres(ql)?://[^:\s]+:[^@\s$]+@", r"-----BEGIN [A-Z ]*PRIVATE KEY-----"]


def fail(msg):
    print("FAIL:", msg)
    sys.exit(1)


def check_skill_md():
    with open(os.path.join(SRC, "SKILL.md"), encoding="utf-8") as fh:
        text = fh.read()
    m = re.match(r"^---\n(.*?)\n---\n(.*)$", text, re.S)
    if not m:
        fail("SKILL.md must start with YAML frontmatter between --- lines")
    front, body = m.groups()
    keys = [ln.split(":", 1)[0].strip() for ln in front.splitlines() if ln and not ln.startswith(" ")]
    if keys != ["name", "description"]:
        fail(f"frontmatter keys must be exactly name, description (got {keys})")
    name = re.search(r"^name:\s*(\S+)\s*$", front, re.M).group(1)
    if name != SKILL or not re.fullmatch(r"[a-z0-9]+(-[a-z0-9]+)*", name):
        fail(f"name '{name}' must equal folder '{SKILL}' and be a lowercase slug")
    desc = re.search(r"^description:\s*(.+)$", front, re.M).group(1).strip()
    if len(desc) < 40:
        fail("description too short")
    if ":" in desc.replace("e.g.", "") and not desc.startswith(('"', "'")):
        # unquoted colons can break strict YAML parsers
        if re.search(r":\s", desc):
            fail("description contains ': ' — quote it or rephrase")
    if len(body.strip()) < 200:
        fail("SKILL.md body is empty or too short")
    print(f"ok  SKILL.md (name={name}, description {len(desc)} chars)")


def collect():
    files = []
    for root, dirs, names in os.walk(SRC):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for n in names:
            p = os.path.join(root, n)
            rel = os.path.relpath(p, HERE).replace(os.sep, "/")
            if n in SKIP_FILES or n.endswith(".pyc"):
                continue
            if os.path.islink(p):
                fail(f"symlink not allowed: {rel}")
            if os.path.splitext(n)[1].lower() not in TEXT_EXT:
                fail(f"non-text file type: {rel}")
            with open(p, "rb") as fh:
                data = fh.read()
            if b"\x00" in data:
                fail(f"binary content: {rel}")
            txt = data.decode("utf-8")
            for pat in SECRET_PATTERNS:
                if re.search(pat, txt):
                    fail(f"possible secret ({pat}) in {rel}")
            files.append((p, rel))
    return sorted(files, key=lambda x: x[1])


def main():
    check_skill_md()
    files = collect()
    os.makedirs(DIST, exist_ok=True)
    out = os.path.join(DIST, f"{SKILL}.zip")
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for p, rel in files:
            info = zipfile.ZipInfo(rel, date_time=(2026, 1, 1, 0, 0, 0))
            mode = 0o755 if rel.endswith(".py") and "/scripts/" in rel and not rel.endswith("_common.py") else 0o644
            info.external_attr = (stat.S_IFREG | mode) << 16
            info.compress_type = zipfile.ZIP_DEFLATED
            with open(p, "rb") as fh:
                z.writestr(info, fh.read())
    with zipfile.ZipFile(out) as z:
        tops = {n.split("/")[0] for n in z.namelist()}
        if tops != {SKILL} or f"{SKILL}/SKILL.md" not in z.namelist():
            fail(f"bad zip layout: {tops}")
    print(f"ok  {len(files)} text files, layout {SKILL}/SKILL.md")
    print(f"built {out} ({os.path.getsize(out) / 1024:.1f} KB)")


if __name__ == "__main__":
    main()
