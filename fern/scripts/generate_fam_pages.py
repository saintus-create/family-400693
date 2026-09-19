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

    # One page per Division, except SPLIT_DIVISIONS which get one page per
    # Part (or per Chapter when the Division has no Parts).
    SPLIT_DIVISIONS = {"9", "17"}
    groups = OrderedDict()
    for s in sections:
        groups.setdefault(s["division"], []).append(s)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for old in OUT_DIR.glob("*.mdx"):
        old.unlink()

    nav_by_div = OrderedDict()      # (dnum, dtitle) -> [(label, path)] or path
    overview_by_div = OrderedDict() # (dnum, dtitle) -> [(label, href, first, last, n)]
    pages = []

    def write_page(fname, slug, page_title, description, crumb, secs, top_level):
        first, last = secs[0]["section"], secs[-1]["section"]
        lines = [
            "---",
            f"title: {json.dumps(page_title, ensure_ascii=False)}",
            f"description: {json.dumps(description, ensure_ascii=False)}",
            f"slug: {slug}",
            "---",
            "",
            f"{crumb} · §§ {esc(first)}–{esc(last)} · {len(secs)} sections · [Family Code overview](/codes/fam)",
            "",
        ]
        cur = {"part": object(), "chapter": object(), "article": object()}
        for s in secs:
            if s["part"] != cur["part"]:
                cur["part"] = s["part"]; cur["chapter"] = object(); cur["article"] = object()
                if cur["part"] and "part" in top_level:
                    n, t = split_label(cur["part"])
                    lines += [f"## Part {esc(n)}. {esc(t)}", ""]
            if s["chapter"] != cur["chapter"]:
                cur["chapter"] = s["chapter"]; cur["article"] = object()
                if cur["chapter"]:
                    n, t = split_label(cur["chapter"])
                    if "chapter" in top_level:
                        lines += [f"## Chapter {esc(n)}. {esc(t)}", ""]
                    elif "article" not in top_level:
                        lines += [f"**Chapter {esc(n)}. {esc(t)}**", ""]
            if s["article"] != cur["article"]:
                cur["article"] = s["article"]
                if cur["article"]:
                    n, t = split_label(cur["article"])
                    if "article" in top_level:
                        lines += [f"## Article {esc(n)}. {esc(t)}", ""]
                    else:
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
        return first, last

    for div, secs in groups.items():
        dnum, dtitle = split_label(div)
        dslug = slug_num(dnum)
        key = (dnum, dtitle)
        if dnum not in SPLIT_DIVISIONS:
            fname = f"division-{dslug}.mdx"
            slug = f"codes/fam/division-{dslug}"
            title = f"Division {dnum}. {dtitle}"
            desc = f"California Family Code Division {dnum} ({dtitle}) — sections {secs[0]['section']} to {secs[-1]['section']}, {len(secs)} sections with full text."
            first, last = write_page(fname, slug, title, desc, f"California Family Code · Division {esc(dnum)}", secs, {"part", "chapter"})
            nav_by_div[key] = f"docs/pages/codes/fam/{fname}"
            overview_by_div[key] = [(None, f"/{slug}", first, last, len(secs))]
            continue

        unit = "part" if any(s["part"] for s in secs) else "chapter"
        sub = OrderedDict()
        for s in secs:
            sub.setdefault(s[unit], []).append(s)
        nav_by_div[key] = []
        overview_by_div[key] = []
        for label, ssecs in sub.items():
            unum, utitle = split_label(label)
            uname = unit.capitalize()
            fname = f"division-{dslug}-{unit}-{slug_num(unum)}.mdx"
            slug = f"codes/fam/division-{dslug}-{unit}-{slug_num(unum)}"
            title = f"Division {dnum}, {uname} {unum}. {utitle}"
            desc = f"California Family Code Division {dnum} ({dtitle}), {uname} {unum} ({utitle}) — sections {ssecs[0]['section']} to {ssecs[-1]['section']}, {len(ssecs)} sections with full text."
            crumb = f"California Family Code · Division {esc(dnum)}. {esc(dtitle)} › {uname} {esc(unum)}. {esc(utitle)}"
            first, last = write_page(fname, slug, title, desc, crumb, ssecs, {"chapter"} if unit == "part" else {"article"})
            nav_by_div[key].append((f"{uname} {unum}. {utitle}", f"docs/pages/codes/fam/{fname}"))
            overview_by_div[key].append((f"{uname} {unum}. {utitle}", f"/{slug}", first, last, len(ssecs)))

    # Overview page.
    ov = [
        "---",
        "title: Family Code",
        f"description: Browse all {len(sections):,} sections of the California Family Code by Division.",
        "slug: codes/fam",
        "---",
        "",
        f"**{len(sections):,} sections** · **{len(pages)} browsable pages** · **Snapshot updated by the source: November 27, 2025**",
        "",
        "The California Family Code is organized into Divisions, rendered one page per Division below (Divisions 9 and 17 are split into one page per Part or Chapter), with the full statutory text, section by section, with the legislative history for each section.",
        "",
        "<Note>",
        "The text is a dated research snapshot. Verify the current text, effective date, and applicability against the [official California Legislative Information](https://leginfo.legislature.ca.gov/faces/codes.xhtml) source before relying on a provision.",
        "</Note>",
        "",
    ]
    ov += ["## Divisions", ""]
    for (dnum, dtitle), entries in overview_by_div.items():
        if entries[0][0] is None:
            _, href, first, last, n = entries[0]
            ov.append(f"- [Division {esc(dnum)}. {esc(dtitle)}]({href}) — §§ {esc(first)}–{esc(last)} ({n} sections)")
        else:
            ov.append(f"- Division {esc(dnum)}. {esc(dtitle)}")
            for label, href, first, last, n in entries:
                ov.append(f"  - [{esc(label)}]({href}) — §§ {esc(first)}–{esc(last)} ({n} sections)")
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
    for (dnum, dtitle), entry in nav_by_div.items():
        label = json.dumps(f"Division {dnum}. {dtitle}", ensure_ascii=False)
        if isinstance(entry, str):
            out.append(f"{ind}    - page: {label}")
            out.append(f"{ind}      path: {entry}")
        else:
            out.append(f"{ind}    - section: {label}")
            out.append(f"{ind}      contents:")
            for plabel, path in entry:
                out.append(f"{ind}        - page: {json.dumps(plabel, ensure_ascii=False)}")
                out.append(f"{ind}          path: {path}")
    print("\n".join(out))
    print(f"# {len(pages)} pages written", file=sys.stderr)


if __name__ == "__main__":
    main()
