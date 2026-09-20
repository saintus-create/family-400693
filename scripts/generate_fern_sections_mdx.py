#!/usr/bin/env python3
"""Generate Fern MDX per California code section.

Converts the compressed JSONL corpus at fern/docs/assets/corpus/law/*.jsonl.gz
into Fern-compatible MDX under fern/docs/pages/codes/sections/<code>/*.mdx

Each section becomes one MDX file with frontmatter (title, description, slug, position)
and a structured body (text, history, hierarchy, official LegInfo link).

Usage:
  python3 scripts/generate_fern_sections_mdx.py                 # all 30 codes, ~162k files
  python3 scripts/generate_fern_sections_mdx.py --code FAM      # single code
  python3 scripts/generate_fern_sections_mdx.py --code FAM --code CONS
  python3 scripts/generate_fern_sections_mdx.py --code FAM --limit 10
  python3 scripts/generate_fern_sections_mdx.py --clean         # remove existing generated sections first

Fern navigation:
  Add ONE folder entry in fern/docs.yml (see docs below). Fern auto-discovers
  all *.mdx under that folder, so you do NOT need to list 162k pages manually.

  Example docs.yml addition:

    - section: Code Sections (MDX — 162k)
      collapsed: true
      contents:
        - folder: docs/pages/codes/sections
          title: All sections
          slug: codes/sections
          title-source: frontmatter

  Each MDX page sets slug: codes/<code>/<section-id> so the final URL is
  citation-friendly (e.g. /codes/fam/1, /codes/gov/65914, /codes/cons/I-1)
  even though the file lives under sections/<code>/.

  The script also writes an index.mdx overview at sections/index.mdx
  and per-code index files at sections/<code>/index.mdx.
"""
from __future__ import annotations

import argparse
import gzip
import json
import re
from pathlib import Path
from typing import Iterable

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ASSET_ROOT = REPO_ROOT / "fern" / "docs" / "assets" / "corpus"
DEFAULT_OUTPUT_ROOT = REPO_ROOT / "fern" / "docs" / "pages" / "codes" / "sections"
OFFICIAL_BASE = "https://leginfo.legislature.ca.gov/faces/codes_displaySection.xhtml"

# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def clean_section_slug(uid: str) -> str:
    """Turn UID suffix into a filesystem / URL slug.

    Examples:
      FAM:1          -> 1
      FAM:2211#2     -> 2211-2
      BPC:10-719     -> 10-719
      BPC:10-719#2   -> 10-719-2
      CONS:I-1       -> I-1
      GOV:101.5      -> 101.5

    Keeps A-Z a-z 0-9 . - _ but replaces other chars (like # / :) with '-',
    collapses repeats and strips leading/trailing '-'.
    """
    suffix = uid.split(":", 1)[1] if ":" in uid else uid
    # replace hash marker for duplicate UIDs
    slug = suffix.replace("#", "-")
    # sanitize: keep alphanum, dot, hyphen, underscore
    slug = re.sub(r"[^A-Za-z0-9._\-]", "-", slug)
    slug = re.sub(r"-+", "-", slug).strip("-")
    # avoid empty
    return slug or "section"


def safe_description(text: str, fallback_citation: str) -> str:
    """Short description for frontmatter, YAML-safe."""
    t = (text or "").strip().replace("\n", " ").replace("\r", " ")
    # collapse whitespace
    t = re.sub(r"\s+", " ", t)
    if not t:
        return fallback_citation
    # truncate ~150 chars at word boundary
    if len(t) > 160:
        cut = t[:157]
        # try to cut at last space
        if " " in cut:
            cut = cut.rsplit(" ", 1)[0]
        t = cut.rstrip(" ,.;:") + "…"
    # escape double quotes for YAML inline string
    t = t.replace('"', "'").replace("\n", " ")
    return t


def yaml_escape(value: str) -> str:
    """Escape for YAML double-quoted string."""
    return value.replace("\\", "\\\\").replace('"', '\\"').replace("\n", " ")


def official_url(code: str, section: str) -> str:
    # Official LegInfo pattern: ?sectionNum=<section>.&lawCode=<CODE>
    # Section itself may contain dots/hyphens like 101.5 -> "101.5."
    return f"{OFFICIAL_BASE}?sectionNum={section}.&lawCode={code}"


def records_for_code(asset: Path, code: str) -> Iterable[dict]:
    with gzip.open(asset, "rt", encoding="utf-8") as fh:
        for line in fh:
            if not line.strip():
                continue
            rec = json.loads(line)
            if rec.get("kind") == "section" and rec.get("code") == code:
                yield rec


def build_section_mdx(rec: dict, prev_rec: dict | None, next_rec: dict | None, code_name: str, updated: str | None) -> str:
    code = rec["code"]
    code_lower = code.lower()
    citation = rec.get("citation") or f"{code} § {rec.get('section')}"
    section = str(rec.get("section") or "").strip()
    uid = rec.get("uid") or f"{code}:{section}"
    file_slug = clean_section_slug(uid)
    slug = f"codes/{code_lower}/{file_slug}"
    # position controls ordering in Fern folder; use ordinal if present else 0
    ordinal = rec.get("ordinal")
    position = int(ordinal) if isinstance(ordinal, int) else 0

    title = citation  # keep citation as title so folder title-source=frontmatter shows citation
    description = safe_description(rec.get("text") or "", citation)
    text = (rec.get("text") or "").strip()
    history = (rec.get("history") or "").strip()
    path_hierarchy = (rec.get("path") or "").strip()
    division = rec.get("division")
    part = rec.get("part")
    chapter = rec.get("chapter")
    article = rec.get("article")
    # hierarchy breadcrumb pieces
    hierarchy_parts = [p for p in [division, part, rec.get("title"), chapter, article] if p]
    hierarchy_display = " > ".join(hierarchy_parts) if hierarchy_parts else path_hierarchy or "—"

    repealed = bool(rec.get("repealed"))
    official = official_url(code, section)

    # Prepare navigation links (prev / next) using their file slugs
    nav_parts = []
    if prev_rec:
        prev_uid = prev_rec.get("uid") or f"{code}:{prev_rec.get('section')}"
        prev_slug = clean_section_slug(prev_uid)
        prev_citation = prev_rec.get("citation") or f"{code} § {prev_rec.get('section')}"
        nav_parts.append(f'[← {prev_citation}](/codes/{code_lower}/{prev_slug})')
    if next_rec:
        next_uid = next_rec.get("uid") or f"{code}:{next_rec.get('section')}"
        next_slug = clean_section_slug(next_uid)
        next_citation = next_rec.get("citation") or f"{code} § {next_rec.get('section')}"
        nav_parts.append(f'[{next_citation} →](/codes/{code_lower}/{next_slug})')
    # always add overview + search
    nav_parts.append(f'[Browse {code_name}](/codes/{code_lower})')
    nav_parts.append('[Search corpus](/codes/search)')

    nav_line = " · ".join(nav_parts)

    # Escape text for markdown: preserve paragraph breaks, avoid breaking MDX
    # We'll output text as-is but ensure no triple backtick break.
    # Replace any occurrence of "---" line that could be mistaken for frontmatter? Not needed inside body.
    def md_block(s: str) -> str:
        if not s:
            return "_Not available._"
        # Ensure we don't have MDX comment issues; just return raw
        return s.strip()

    # Build frontmatter with proper escaping
    frontmatter = f'''---
title: "{yaml_escape(title)}"
description: "{yaml_escape(description)}"
slug: {slug}
position: {position}
---
'''

    # Choose admonition based on repealed status
    snapshot_note = f"Snapshot updated by the state: **{updated}** — dated research snapshot. Verify current text and effective date at the [official California Legislative Information source]({official})."

    body_parts = [
        f"# {citation}\n",
        f"<Note>\n{snapshot_note}\n</Note>\n" if not repealed else f"<Warning>\n**Repealed / historical record.** {snapshot_note}\n</Warning>\n",
        f"**Code:** {code_name} (`{code}`) · **Section:** `{section}` · **UID:** `{uid}`\n",
        f"**Location:** {hierarchy_display}\n" if hierarchy_display and hierarchy_display != "—" else "",
        f"**Citation:** {citation} · **Official:** [{official}]({official})\n",
        "---\n",
        "## Text\n",
        md_block(text) + "\n",
        "## History\n",
        md_block(history) + "\n" if history else "_No separate history note in this snapshot._\n",
        "## Metadata\n",
        f"- **Char count:** {rec.get('char_count') or len(text)}\n",
        f"- **Repealed:** {'Yes' if repealed else 'No'}\n",
        f"- **Hierarchy path:** `{path_hierarchy}`\n" if path_hierarchy else "",
        f"- **Division / Part / Chapter / Article:** {hierarchy_display}\n" if hierarchy_display != path_hierarchy else "",
        f"- **Official URL:** [{official}]({official})\n",
        "---\n",
        nav_line + "\n",
    ]

    # Join, filtering empty strings but keeping line breaks
    body = "\n".join(p for p in body_parts if p != "")
    # Ensure body ends with newline
    if not body.endswith("\n"):
        body += "\n"
    return frontmatter + "\n" + body


def per_code_index_mdx(code: str, code_name: str, sections: list[dict], updated: str | None) -> str:
    slug = f"codes/{code.lower()}/sections"
    title = f"{code_name} — Section index"
    desc = f"Index of {len(sections):,} {code_name} sections as Fern MDX"
    frontmatter = f'''---
title: "{yaml_escape(title)}"
description: "{yaml_escape(desc)}"
slug: {slug}
---
'''
    # List sections grouped? For now small table of first 100 + note about full.
    # For per-code folder index we keep it lightweight; the folder navigation itself lists pages.
    lines = [
        f"# {code_name} — Sections\n",
        f"**{len(sections):,} sections** · Snapshot: {updated or 'not stated'} · Code: `{code}`\n",
        f"This index is the Fern overview for the per-section MDX pages under `sections/{code.lower()}/`. Each section is one MDX file and is discoverable via the **Code Sections** folder in the sidebar and via Fern search.\n",
        "<Note>\nDated snapshot — verify at the [official code search](https://leginfo.legislature.ca.gov/faces/codes.xhtml).\n</Note>\n",
        "## Browse\n",
        "Use the left sidebar under **Code Sections → " + code_name + "** to browse sections in statutory order, or use **Search the California Code Corpus** for full-text search.\n",
        "## Quick links (first 50)\n",
    ]
    # List first 50 sections with links using slugs
    for rec in sections[:50]:
        uid = rec.get("uid") or f"{code}:{rec.get('section')}"
        file_slug = clean_section_slug(uid)
        citation = rec.get("citation") or f"{code} § {rec.get('section')}"
        # snippet
        snippet = safe_description(rec.get("text") or "", citation)[:100]
        lines.append(f"- [{citation}](/codes/{code.lower()}/{file_slug}) — {snippet}")
    if len(sections) > 50:
        lines.append(f"\n_… and {len(sections)-50:,} more sections in the sidebar. Use search to find a specific citation._\n")
    lines.append("\n## Files\n")
    lines.append(f"- Compressed source: `fern/docs/assets/corpus/law/{code}.jsonl.gz`")
    lines.append(f"- Corpus manifest: `fern/docs/assets/corpus/manifest.json`")
    return frontmatter + "\n" + "\n".join(lines) + "\n"


def root_index_mdx(datasets: list[dict]) -> str:
    slug = "codes/sections"
    title = "California Code Sections (MDX)"
    desc = "Per-section MDX for 162k California statutory and constitutional sections"
    frontmatter = f'''---
title: "{yaml_escape(title)}"
description: "{yaml_escape(desc)}"
slug: {slug}
---
'''
    total = sum(d["sections"] for d in datasets)
    lines = [
        "# California Code Sections — Per-section MDX\n",
        f"This directory contains **{total:,} sections** across **{len(datasets)} codes** as individual Fern MDX pages under `fern/docs/pages/codes/sections/`.\n",
        "Each section is a first-class Fern page with:\n",
        "- Frontmatter (`title`, `description`, `slug`, `position`) for SEO and ordering\n",
        "- Canonical citation and hierarchy\n",
        "- Operative text and history\n",
        "- Stable `UID` (e.g. `FAM:1`, `CONS:I-1`, `GOV:985#2`) and official LegInfo link\n",
        "- Previous / next navigation in statutory order\n",
        "<Note>\nDated research snapshot — always verify against the [official California Legislative Information](https://leginfo.legislature.ca.gov/faces/codes.xhtml) source.\n</Note>\n",
        "## How to use\n",
        "- **Browse:** expand **Code Sections (MDX)** in the left sidebar, pick a code, then a section. Pages are ordered by `position` (statutory order).\n",
        "- **Search:** use **Search the California Code Corpus** for full-text ranking, then click a citation link which resolves to its MDX page.\n",
        "- **AI search:** Fern Ask Fern can retrieve and cite these pages; they are also synced via `scripts/sync_fern_legal_corpus.py` to the Documents API.\n",
        "- **Build locally:** `python3 scripts/generate_fern_sections_mdx.py --code FAM --limit 5` then `fern check`.\n",
        "## Regenerate\n",
        "```bash\npython3 scripts/generate_fern_sections_mdx.py          # all 162k sections\npython3 scripts/generate_fern_sections_mdx.py --code FAM # just Family Code\npython3 scripts/generate_fern_sections_mdx.py --clean     # clean first\n```\n",
        "## Code catalog\n",
        "| Code | Sections | Folder | Snapshot |\n",
        "| --- | ---: | --- | --- |",
    ]
    for d in sorted(datasets, key=lambda x: x["abbr"]):
        abbr = d["abbr"]
        name = d["name"]
        sec = f"{d['sections']:,}"
        upd = d.get("updated_by_state") or "—"
        lines.append(f"| {name} (`{abbr}`) | {sec} | `sections/{abbr.lower()}/` | {upd} |")
    return frontmatter + "\n" + "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--code", action="append", dest="codes", help="Code abbreviation to generate (e.g. FAM). Repeatable. Default: all.")
    parser.add_argument("--manifest", type=Path, default=DEFAULT_ASSET_ROOT / "manifest.json", help="Path to manifest.json")
    parser.add_argument("--asset-root", type=Path, default=DEFAULT_ASSET_ROOT, help="Directory containing law/*.jsonl.gz")
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT, help="Output directory for MDX sections")
    parser.add_argument("--limit", type=int, default=None, help="Limit sections per code (for testing)")
    parser.add_argument("--clean", action="store_true", help="Remove existing output before generating")
    parser.add_argument("--no-index", action="store_true", help="Skip root/per-code index.mdx generation")
    args = parser.parse_args()

    manifest_path: Path = args.manifest
    asset_root: Path = args.asset_root
    output_root: Path = args.output_root

    if not manifest_path.exists():
        print(f"Missing manifest: {manifest_path}", flush=True)
        return 2
    if not (asset_root / "law").exists():
        print(f"Missing law assets dir: {asset_root / 'law'}", flush=True)
        return 2

    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    datasets = data.get("datasets") or data.get("codes") or []
    if not datasets:
        print("No datasets in manifest", flush=True)
        return 2

    selected = {c.upper() for c in args.codes} if args.codes else None
    filtered = [d for d in datasets if selected is None or d["abbr"].upper() in selected]
    if not filtered:
        print(f"No matching codes for filter {selected}", flush=True)
        return 2

    if args.clean and output_root.exists():
        import shutil
        print(f"Cleaning {output_root} ...")
        shutil.rmtree(output_root)
    output_root.mkdir(parents=True, exist_ok=True)

    total_files = 0
    for ds in sorted(filtered, key=lambda x: x["abbr"]):
        code = ds["abbr"]
        code_name = ds["name"]
        updated = ds.get("updated_by_state")
        asset = asset_root / ds["file"] if "file" in ds else asset_root / "law" / f"{code}.jsonl.gz"
        if not asset.exists():
            # fallback
            asset = asset_root / "law" / f"{code}.jsonl.gz"
        if not asset.exists():
            print(f"⚠ Missing asset for {code}: {asset}")
            continue

        sections = list(records_for_code(asset, code))
        # sort by ordinal to ensure statutory order
        sections.sort(key=lambda r: r.get("ordinal") if isinstance(r.get("ordinal"), int) else 0)
        if args.limit:
            sections = sections[: args.limit]

        code_dir = output_root / code.lower()
        code_dir.mkdir(parents=True, exist_ok=True)

        # Write per-section MDX
        for idx, rec in enumerate(sections):
            prev_rec = sections[idx - 1] if idx > 0 else None
            next_rec = sections[idx + 1] if idx + 1 < len(sections) else None
            mdx = build_section_mdx(rec, prev_rec, next_rec, code_name, updated)
            uid = rec.get("uid") or f"{code}:{rec.get('section')}"
            file_slug = clean_section_slug(uid)
            path = code_dir / f"{file_slug}.mdx"
            # Ensure unique: if file exists due to collision, append ordinal
            if path.exists():
                # This can happen if two UIDs map to same file_slug (rare)
                # Fall back to file_slug + "-" + ordinal
                path = code_dir / f"{file_slug}-{rec.get('ordinal', idx)}.mdx"
            path.write_text(mdx, encoding="utf-8")
            total_files += 1

        # per-code index
        if not args.no_index:
            (code_dir / "index.mdx").write_text(per_code_index_mdx(code, code_name, sections, updated), encoding="utf-8")

        print(f"✓ {code}: wrote {len(sections):,} section MDX → {code_dir}")

    # root index
    if not args.no_index:
        (output_root / "index.mdx").write_text(root_index_mdx(filtered if selected else datasets), encoding="utf-8")
        print(f"✓ index: {output_root / 'index.mdx'}")

    print(f"\nDone. Total section files: {total_files:,} under {output_root}")
    print("Add to fern/docs.yml:\n")
    print("  - section: Code Sections (MDX)")
    print("    collapsed: true")
    print("    contents:")
    print("      - folder: docs/pages/codes/sections")
    print("        title: All sections")
    print("        slug: codes/sections")
    print("        title-source: frontmatter")
    print("\nThen run: fern check")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
