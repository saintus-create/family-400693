#!/usr/bin/env python3
"""Index the California code corpus in Fern Ask Fern.

This is intentionally Fern-native. The JSONL.gz files are repository assets for
the human-facing site, but static assets are not automatically part of Ask Fern's
retrieval index. This script sends section records to Fern's Documents API.

Required environment:
  FERN_AI_TOKEN   Fern Ask Fern/Documents API token

Optional environment:
  FERN_AI_DOMAIN  Defaults to legislature.docs.buildwithfern.com
  FERN_AI_BASEPATH  Defaults to empty/root
  FERN_AI_PRODUCT  Defaults to California Codes
  FERN_AI_VERSION  Defaults to the corpus generated_at timestamp
  FERN_AI_BATCH_SIZE  Defaults to 100
  FERN_AI_CONCURRENCY  Defaults to 4

Usage:
  FERN_AI_TOKEN=... python3 scripts/sync_fern_legal_corpus.py
  FERN_AI_TOKEN=... python3 scripts/sync_fern_legal_corpus.py --code FAM
  FERN_AI_TOKEN=... python3 scripts/sync_fern_legal_corpus.py --replace
"""
from __future__ import annotations

import argparse
import gzip
import json
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

API_ROOT = "https://fai.buildwithfern.com"
DEFAULT_DOMAIN = "legislature.docs.buildwithfern.com"
OFFICIAL_ROOT = "https://leginfo.legislature.ca.gov/faces/codes_displaySection.xhtml"


def env_int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, default))
    except ValueError:
        return default


def official_url(code: str, section: str) -> str:
    return f"{OFFICIAL_ROOT}?sectionNum={section}.&lawCode={code}"


def document_for(rec: dict, version: str, product: str) -> dict:
    code = rec["code"]
    section = str(rec.get("section") or "").strip()
    citation = rec.get("citation") or f"{code} § {section}"
    history = (rec.get("history") or "").strip()
    path = " > ".join(
        str(x).strip()
        for x in (
            rec.get("division"),
            rec.get("part"),
            rec.get("title"),
            rec.get("chapter"),
            rec.get("article"),
        )
        if x
    )

    metadata = [
        f"Code: {code}",
        f"Section: {section}",
        f"Citation: {citation}",
    ]
    if path:
        metadata.append(f"Hierarchy: {path}")
    if history:
        metadata.append(f"History: {history}")

    document = "\n\n".join(
        [
            f"# {citation}",
            "\n".join(metadata),
            "",
            str(rec.get("text") or "").strip(),
            "",
            "California Legislative Information research snapshot.",
        ]
    ).strip()

    keywords = [
        code,
        section,
        citation,
        "California law",
        "California statute",
    ]
    keywords.extend(
        str(x).strip()
        for x in (rec.get("division"), rec.get("part"), rec.get("title"), rec.get("chapter"))
        if x
    )
    keywords = list(dict.fromkeys(k for k in keywords if k))

    return {
        "authed": False,
        "document": document,
        # Keep the vectorized field focused on the statutory provision and
        # citation metadata. Fern handles downstream chunking/retrieval.
        "chunk": document,
        "keywords": keywords,
        "product": product,
        "title": citation,
        "url": official_url(code, section),
        "version": version,
    }


def api_request(
    token: str,
    domain: str,
    path: str,
    payload,
    basepath: str,
):
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    if basepath:
        headers["x-fern-basepath"] = basepath

    req = Request(
        f"{API_ROOT}/document/{domain}/{path}",
        data=json.dumps(payload).encode("utf-8"),
        headers=headers,
        method="POST" if path != "delete" else "DELETE",
    )
    with urlopen(req, timeout=120) as response:
        raw = response.read().decode("utf-8")
        return json.loads(raw) if raw else {}


def delete_existing(token: str, domain: str, basepath: str, prefix: str) -> None:
    url = f"{API_ROOT}/document/{domain}?url_prefix={prefix}"
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}
    if basepath:
        headers["x-fern-basepath"] = basepath
    req = Request(url, headers=headers, method="DELETE")
    with urlopen(req, timeout=120) as response:
        response.read()


def read_records(asset: Path, code: str):
    with gzip.open(asset, "rt", encoding="utf-8") as fh:
        for line in fh:
            if not line.strip():
                continue
            rec = json.loads(line)
            if rec.get("kind") == "section" and rec.get("code") == code:
                yield rec


def upload_batch(
    token: str,
    domain: str,
    basepath: str,
    batch: list[dict],
) -> int:
    api_request(token, domain, "batch-create", batch, basepath)
    return len(batch)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--code", action="append", help="Code abbreviation, e.g. FAM or GOV. Repeatable.")
    parser.add_argument("--replace", action="store_true", help="Delete existing corpus documents before uploading.")
    args = parser.parse_args()

    token = os.environ.get("FERN_AI_TOKEN")
    if not token:
        print("FERN_AI_TOKEN is required.", file=sys.stderr)
        return 2

    root = Path(__file__).resolve().parents[1]
    asset_root = root / "fern" / "docs" / "assets" / "corpus"
    manifest_path = asset_root / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    domain = os.environ.get("FERN_AI_DOMAIN", DEFAULT_DOMAIN)
    basepath = os.environ.get("FERN_AI_BASEPATH", "")
    product = os.environ.get("FERN_AI_PRODUCT", "California Codes")
    version = os.environ.get("FERN_AI_VERSION", manifest["generated_at"])
    batch_size = max(1, env_int("FERN_AI_BATCH_SIZE", 100))
    concurrency = max(1, env_int("FERN_AI_CONCURRENCY", 4))

    selected = {x.upper() for x in args.code} if args.code else None
    datasets = [
        d for d in manifest["datasets"]
        if selected is None or d["abbr"].upper() in selected
    ]

    if not datasets:
        print("No matching code datasets.", file=sys.stderr)
        return 2

    if args.replace:
        prefix = "https://leginfo.legislature.ca.gov/faces/codes_displaySection.xhtml"
        print("Deleting existing California-code Documents API records...")
        delete_existing(token, domain, basepath, prefix)

    batches: list[list[dict]] = []
    total = 0

    for dataset in datasets:
        code = dataset["abbr"]
        asset = asset_root / dataset["file"]
        if not asset.exists():
            print(f"Missing corpus asset: {asset}", file=sys.stderr)
            return 2

        batch: list[dict] = []
        count = 0
        for rec in read_records(asset, code):
            batch.append(document_for(rec, version, product))
            count += 1
            if len(batch) >= batch_size:
                batches.append(batch)
                batch = []
        if batch:
            batches.append(batch)
        total += count
        print(f"{code}: prepared {count:,} statutory sections")

    print(
        f"Uploading {total:,} sections to Fern Ask Fern "
        f"in {len(batches):,} batches with concurrency={concurrency}..."
    )

    uploaded = 0
    failures: list[str] = []

    def send(i_batch: tuple[int, list[dict]]) -> tuple[int, int, str | None]:
        index, batch = i_batch
        for attempt in range(4):
            try:
                return index, upload_batch(token, domain, basepath, batch), None
            except (HTTPError, URLError, TimeoutError) as exc:
                if attempt == 3:
                    return index, 0, str(exc)
                time.sleep(2**attempt)
        return index, 0, "unreachable"

    with ThreadPoolExecutor(max_workers=concurrency) as pool:
        futures = [pool.submit(send, item) for item in enumerate(batches, 1)]
        for future in as_completed(futures):
            index, count, error = future.result()
            if error:
                failures.append(f"batch {index}: {error}")
                print(f"FAILED {index}/{len(batches)}: {error}", file=sys.stderr)
            else:
                uploaded += count
                print(f"uploaded batch {index}/{len(batches)} ({count} sections)")

    if failures:
        print(f"\nUploaded {uploaded:,}/{total:,}. Failures:", file=sys.stderr)
        print("\n".join(failures), file=sys.stderr)
        return 1

    print(f"Indexed {uploaded:,} California statutory sections in Fern Ask Fern.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
