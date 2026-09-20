#!/usr/bin/env python3
"""Package the canonical California law snapshot for the Fern docs site.

The corpus stays section-level and compressed. Fern receives a browsable catalog,
per-code overview pages, a machine-readable manifest, and downloadable JSONL
snapshots. The same snapshot can be rendered as per-section Fern MDX via
scripts/generate_fern_sections_mdx.py (~162k pages), which is additive and
kept alongside the compressed assets — the catalog remains lightweight while
the optional folder `fern/docs/pages/codes/sections/` holds the full MDX.
"""
from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

OFFICIAL_CODES_URL = "https://leginfo.legislature.ca.gov/faces/codes.xhtml"
REPO_ASSET_URL = "https://github.com/saintus-create/family-400693/blob/main/fern/docs/assets/corpus"


def slug(value: str) -> str:
    return value.lower().replace(" ", "-").replace("/", "-")


def page_for(code: dict) -> str:
    abbr = code["abbr"]
    name = code["name"]
    sections = f"{code['sections']:,}"
    records = f"{code['records']:,}"
    updated = code.get("updated_by_state") or "not stated"
    filename = code["file"]
    code_slug = slug(abbr)
    return f'''---
title: {name}
description: Section-level {name} corpus with {sections} sections.
slug: codes/{code_slug}
---

# {name}

**{sections} sections** · **{records} records including hierarchy nodes** · **Snapshot updated by the source: {updated}**

This page is the Fern catalog entry for the `{abbr}` dataset. The complete section-level snapshot is preserved as compressed JSON Lines so it can be downloaded, mirrored, or indexed by a downstream search service. The same data is also rendered as **per-section MDX pages** under `Code Sections (MDX)` — one Fern MDX page per section (e.g. `/codes/{code_slug}/1`), generated from the canonical corpus.

## Files

- [Download the `{filename}` dataset]({REPO_ASSET_URL}/law/{filename})
- [Download the corpus manifest]({REPO_ASSET_URL}/manifest.json)
- [Browse the official California code search](https://leginfo.legislature.ca.gov/faces/codes.xhtml)
- [Browse {name} MDX sections](/codes/sections) — navigate `sections/{code_slug}/` in the sidebar

## MDX generation

Regenerate the catalog and/or the per-section MDX from the canonical `data/law/*.jsonl.gz` snapshot:

```bash
# catalog (overview pages + compressed assets)
python3 scripts/build_fern_corpus.py /path/to/source/checkout

# per-section MDX (one .mdx per statutory section)
python3 scripts/generate_fern_sections_mdx.py --code {abbr}   # single code
python3 scripts/generate_fern_sections_mdx.py                 # all 30 codes (~162k files)
```

## Record format

Each JSONL record is either a `section` or a table-of-contents node. Section records retain the citation, operative text, history, repeal status, hierarchy path, and a stable UID such as `{abbr}:1`.

```json
{{
  "kind": "section",
  "code": "{abbr}",
  "citation": "{abbr} § …",
  "section": "…",
  "text": "…",
  "history": "…"
}}
```

<Note>
The dataset is a dated research snapshot. Verify the current text, effective date, and applicability against the official California Legislative Information source before relying on a provision.
</Note>
'''


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source_root", type=Path, help="checkout containing data/MANIFEST.json")
    parser.add_argument("target_root", type=Path, nargs="?", default=Path("."))
    args = parser.parse_args()
    source_root = args.source_root.resolve()
    target_root = args.target_root.resolve()
    source_manifest = source_root / "data" / "MANIFEST.json"
    asset_root = target_root / "fern" / "docs" / "assets" / "corpus"
    law_asset_root = asset_root / "law"
    page_root = target_root / "fern" / "docs" / "pages" / "codes"
    manifest = json.loads(source_manifest.read_text(encoding="utf-8"))
    codes = sorted(manifest["codes"], key=lambda item: item["display_order"])

    if len(codes) != 30:
        raise SystemExit(f"expected 30 datasets, found {len(codes)}")

    law_asset_root.mkdir(parents=True, exist_ok=True)
    page_root.mkdir(parents=True, exist_ok=True)

    for old in law_asset_root.glob("*.jsonl.gz"):
        old.unlink()
    for old in page_root.glob("*.mdx"):
        if old.name in {"index.mdx", "search.mdx"}:
            continue
        old.unlink()

    catalog = {
        "format": "fern-corpus-index-v1",
        "generated_at": manifest["generated_at"],
        "source": manifest["source"],
        "official_source": OFFICIAL_CODES_URL,
        "datasets": [],
    }

    for code in codes:
        source = source_root / "data" / "law" / code["file"]
        target = law_asset_root / code["file"]
        if not source.exists():
            raise SystemExit(f"missing source dataset: {source}")
        shutil.copy2(source, target)
        page_path = page_root / f"{slug(code['abbr'])}.mdx"
        page_path.write_text(page_for(code), encoding="utf-8")
        catalog["datasets"].append(
            {
                "abbr": code["abbr"],
                "name": code["name"],
                "slug": slug(code["abbr"]),
                "file": f"law/{code['file']}",
                "sections": code["sections"],
                "records": code["records"],
                "headings": code["headings"],
                "char_count": code["char_count"],
                "updated_by_state": code.get("updated_by_state"),
                "sha256": code["sha256"],
            }
        )

    (asset_root / "manifest.json").write_text(json.dumps(catalog, indent=2) + "\n", encoding="utf-8")
    (asset_root / "README.md").write_text(
        "# Fern corpus assets\n\n"
        "This directory contains the complete section-level California law snapshot "
        "packaged for the Fern documentation site. See `manifest.json` for provenance "
        "and checksums.\n",
        encoding="utf-8",
    )
    print(json.dumps({"datasets": len(codes), "sections": sum(c["sections"] for c in codes), "asset_root": str(asset_root)}))


if __name__ == "__main__":
    main()
