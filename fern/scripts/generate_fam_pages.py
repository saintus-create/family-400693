#!/usr/bin/env python3
"""Generate browsable Family Code MDX pages from the FAM corpus.

Reads docs/assets/corpus/law/FAM.jsonl(.gz), groups sections by Division,
writes one MDX page per Division under docs/pages/codes/fam/, rewrites docs/pages/codes/fam.mdx as the
overview, and prints the docs.yml navigation block to stdout.
"""
import gzip
import json
import re
import sys
from collections import OrderedDict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CORPUS = ROOT / "docs/assets/corpus/law/FAM.jsonl.gz"
OUT_DIR = ROOT / "docs/pages/codes/fam"
OVERVIEW = ROOT / "docs/pages/codes/fam.mdx"

ESCAPE_RE = re.compile(r"([\\`*_{}\[\]<>|~$#])")


def esc(text: str) -> str:
    return ESCAPE_RE.sub(r"\\\1", text or "")


def split_label(label):
    """'2.5. DOMESTIC PARTNER REGISTRATION' -> ('2.5', 'Domestic Partner Registration')."""
    m = re.match(r"^([\d.]+?)\.\s+(.*)$", label)
    if not m:
        return None, label.strip()
    num, title = m.group(1), m.group(2).strip()
    if title.isupper():
        title = title.title().replace("'S", "'s").replace(" And ", " and ").replace(" Of ", " of ").replace(" In ", " in ").replace(" To ", " to ").replace(" For ", " for ").replace(" On ", " on ").replace(" By ", " by ").replace(" Or ", " or ")
    return num, title


def slug_num(num):
    return num.replace(".", "-")


def load():
    opener = gzip.open if CORPUS.suffix == ".gz" else open
    with opener(CORPUS, "rt", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                yield json.loads(line)


def main():
    sections = [r for r in load() if r["kind"] == "section"]
    sections.sort(key=lambda r: r["ordinal"])

    # One page per Division.
    groups = OrderedDict()
    for s in sections:
        groups.setdefault(s["division"], []).append(s)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for old in OUT_DIR.glob("*.mdx"):
        old.unlink()

    nav_by_div = OrderedDict()
    overview_by_div = OrderedDict()
    pages = []

    for div, secs in groups.items():
        dnum, dtitle = split_label(div)
        fname = f"division-{slug_num(dnum)}.mdx"
        slug = f"codes/fam/division-{slug_num(dnum)}"
        first, last = secs[0]["section"], secs[-1]["section"]
        page_title = f"Division {dnum}. {dtitle}"
        description = f"California Family Code Division {dnum} ({dtitle}) — sections {first} to {last}, {len(secs)} sections with full text."

        lines = [
            "---",
            f"title: {json.dumps(page_title, ensure_ascii=False)}",
            f"description: {json.dumps(description, ensure_ascii=False)}",
            f"slug: {slug}",
            "---",
            "",
            f"California Family Code · Division {esc(dnum)} · §§ {esc(first)}–{esc(last)} · {len(secs)} sections · [Family Code overview](/codes/fam)",
            "",
        ]

        cur = {"part": object(), "chapter": object(), "article": object()}
        parts_seen = []
        for s in secs:
            if s["part"] != cur["part"]:
                cur["part"] = s["part"]; cur["chapter"] = object(); cur["article"] = object()
                if cur["part"]:
                    n, t = split_label(cur["part"])
                    lines += [f"## Part {esc(n)}. {esc(t)}", ""]
                    parts_seen.append(f"Part {n}. {t}")
            if s["chapter"] != cur["chapter"]:
                cur["chapter"] = s["chapter"]; cur["article"] = object()
                if cur["chapter"]:
                    n, t = split_label(cur["chapter"])
                    lines += [f"**Chapter {esc(n)}. {esc(t)}**", ""]
            if s["article"] != cur["article"]:
                cur["article"] = s["article"]
                if cur["article"]:
                    n, t = split_label(cur["article"])
                    lines += [f"*Article {esc(n)}. {esc(t)}*", ""]
            head = f"### § {esc(s['section'])}"
            if s.get("repealed"):
                head += " (Repealed)"
            lines += [head, ""]
            text = (s.get("text") or "").strip()
            if text:
                for para in re.split(r"\n\s*\n", text):
                    para = " ".join(p.strip() for p in para.splitlines())
                    lines += [esc(para), ""]
            if s.get("history"):
                lines += [f"*{esc(s['history'].strip())}*", ""]

        (OUT_DIR / fname).write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
        pages.append(fname)
        nav_by_div[(dnum, dtitle)] = f"docs/pages/codes/fam/{fname}"
        overview_by_div[(dnum, dtitle)] = (f"/{slug}", first, last, len(secs), parts_seen)

    # Overview page.
    ov = [
        "---",
        "title: Family Code",
        f"description: Browse all {len(sections):,} sections of the California Family Code by Division.",
        "slug: codes/fam",
        "---",
        "",
        f"**{len(sections):,} sections** · **{len(pages)} Division pages** · **Snapshot updated by the source: November 27, 2025**",
        "",
        "The California Family Code is organized into Divisions, each of which is rendered on a single page below with the full statutory text, section by section, grouped by Part, Chapter, and Article, with the legislative history for each section.",
        "",
        "<Note>",
        "The text is a dated research snapshot. Verify the current text, effective date, and applicability against the [official California Legislative Information](https://leginfo.legislature.ca.gov/faces/codes.xhtml) source before relying on a provision.",
        "</Note>",
        "",
    ]
    ov += ["## Divisions", ""]
    for (dnum, dtitle), (href, first, last, n, parts_seen) in overview_by_div.items():
        ov.append(f"- [Division {esc(dnum)}. {esc(dtitle)}]({href}) — §§ {esc(first)}–{esc(last)} ({n} sections)")
        for pt in parts_seen:
            ov.append(f"  - {esc(pt)}")
    ov.append("")
    ov += [
        "## Data",
        "",
        "- [Download the `FAM.jsonl.gz` dataset](https://github.com/saintus-create/family-400693/blob/main/fern/docs/assets/corpus/law/FAM.jsonl.gz)",
        "- [Search the California Code corpus](/codes/search)",
        "",
    ]
    OVERVIEW.write_text("\n".join(ov), encoding="utf-8")

    # docs.yml block.
    ind = "          "
    out = [f"{ind}- section: Family Code", f"{ind}  path: docs/pages/codes/fam.mdx", f"{ind}  contents:"]
    for (dnum, dtitle), path in nav_by_div.items():
        out.append(f"{ind}    - page: {json.dumps(f'Division {dnum}. {dtitle}', ensure_ascii=False)}")
        out.append(f"{ind}      path: {path}")
    print("\n".join(out))
    print(f"# {len(pages)} pages written", file=sys.stderr)


if __name__ == "__main__":
    main()
