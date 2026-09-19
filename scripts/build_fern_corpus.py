#!/usr/bin/env python3
"""Package the canonical California law snapshot for the Fern docs site.

The corpus stays section-level and compressed. Fern receives a browsable catalog,
per-code overview pages, a machine-readable manifest, and downloadable JSONL
snapshots instead of 162k individual MDX pages.
"""
from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

OFFICIAL_CODES_URL = "https://leginfo.legislature.ca.gov/faces/codes.xhtml"


def slug(value: str) -> str:
    return value.lower().replace(" ", "-").replace("/", "-")


def page_for(code: dict) -> str:
    abbr = code["abbr"]
    name = code["name"]
    sections = f"{code['sections']:,}"
    records = f"{code['records']:,}"
    updated = code.get("updated_by_state") or "not stated"
    filename = code["file"]
    return f'''---
title: {name}
description: Section-level {name} corpus with {sections} sections.
slug: codes/{slug(abbr)}
---

# {name}

**{sections} sections** · **{records} records including hierarchy nodes** · **Snapshot updated by the source: {updated}**

This page is the Fern catalog entry for the `{abbr}` dataset. The complete section-level snapshot is preserved as compressed JSON Lines so it can be downloaded, mirrored, or indexed by a downstream search service without generating one fragile documentation page per section.

## Files

- [Download the `{filename}` dataset](/assets/corpus/law/{filename})
- [Download the corpus manifest](/assets/corpus/manifest.json)
- [Browse the official California code search](https://leginfo.legislature.ca.gov/faces/codes.xhtml)

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
        if old.name != "index.mdx":
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
