#!/usr/bin/env python3
"""Generate browsable Family Code MDX pages from the FAM corpus.

Reads docs/assets/corpus/law/FAM.jsonl(.gz), groups sections by Division and
Part (splitting oversized parts by Chapter/Article), writes one MDX page per
group under docs/pages/codes/fam/, rewrites docs/pages/codes/fam.mdx as the
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
MAX_CHARS = 150_000

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

    # Group by (division, part).
    groups = OrderedDict()
    for s in sections:
        groups.setdefault((s["division"], s["part"]), []).append(s)

    # Split oversized groups by chapter, then article.
    pages = []  # (division, part, chapter, article, sections)
    for (div, part), secs in groups.items():
        total = sum(s["char_count"] for s in secs)
        if total <= MAX_CHARS:
            pages.append((div, part, None, None, secs))
            continue
        by_ch = OrderedDict()
        for s in secs:
            by_ch.setdefault(s["chapter"], []).append(s)
        for ch, chsecs in by_ch.items():
            if sum(s["char_count"] for s in chsecs) <= MAX_CHARS or ch is None:
                pages.append((div, part, ch, None, chsecs))
                continue
            by_art = OrderedDict()
            for s in chsecs:
                by_art.setdefault(s["article"], []).append(s)
            for art, artsecs in by_art.items():
                pages.append((div, part, ch, art, artsecs))

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for old in OUT_DIR.glob("*.mdx"):
        old.unlink()

    nav_by_div = OrderedDict()
    overview_by_div = OrderedDict()

    for div, part, ch, art, secs in pages:
        dnum, dtitle = split_label(div)
        slug_parts = [f"division-{slug_num(dnum)}"]
        title_bits = [f"Division {dnum}"]
        heading_bits = [f"Division {dnum}. {dtitle}"]
        if part:
            pnum, ptitle = split_label(part)
            slug_parts.append(f"part-{slug_num(pnum)}")
            title_bits.append(f"Part {pnum}")
            heading_bits.append(f"Part {pnum}. {ptitle}")
            nav_label = f"Part {pnum}. {ptitle}"
        else:
            nav_label = dtitle
        if ch:
            cnum, ctitle = split_label(ch)
            slug_parts.append(f"chapter-{slug_num(cnum)}")
            title_bits.append(f"Chapter {cnum}")
            heading_bits.append(f"Chapter {cnum}. {ctitle}")
            nav_label = (f"{nav_label} — " if part else "") + f"Chapter {cnum}. {ctitle}"
        if art:
            anum, atitle = split_label(art)
            slug_parts.append(f"article-{slug_num(anum)}")
            title_bits.append(f"Article {anum}")
            heading_bits.append(f"Article {anum}. {atitle}")
            nav_label = f"{nav_label}, Article {anum}. {atitle}"

        fname = "-".join(slug_parts) + ".mdx"
        slug = "codes/fam/" + "-".join(slug_parts)
        first, last = secs[0]["section"], secs[-1]["section"]
        page_title = f"Family Code {', '.join(title_bits)}"
        description = f"{heading_bits[-1]} — Family Code sections {first} to {last} ({len(secs)} sections)."

        lines = [
            "---",
            f"title: {json.dumps(page_title, ensure_ascii=False)}",
            f"description: {json.dumps(description, ensure_ascii=False)}",
            f"slug: {slug}",
            "---",
            "",
            "**" + esc(" › ".join(heading_bits)) + "**",
            "",
            f"Family Code §§ {esc(first)}–{esc(last)} · {len(secs)} sections · [Family Code overview](/codes/fam)",
            "",
        ]

        cur_ch = cur_art = object()
        for s in secs:
            if not ch and s["chapter"] != cur_ch:
                cur_ch = s["chapter"]
                cur_art = object()
                if cur_ch:
                    n, t = split_label(cur_ch)
                    lines += [f"## Chapter {esc(n)}. {esc(t)}", ""]
            if not art and s["article"] != cur_art:
                cur_art = s["article"]
                if cur_art:
                    n, t = split_label(cur_art)
                    lines += [f"### Article {esc(n)}. {esc(t)}", ""]
            heading_level = "####" if (s["chapter"] and not ch) else "##"
            head = f"{heading_level} § {esc(s['section'])}"
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

        nav_by_div.setdefault((dnum, dtitle), []).append((nav_label, f"docs/pages/codes/fam/{fname}"))
        overview_by_div.setdefault((dnum, dtitle), []).append((nav_label, f"/{slug}", first, last, len(secs)))

    # Overview page.
    ov = [
        "---",
        "title: Family Code",
        f"description: Browse all {len(sections):,} sections of the California Family Code by Division and Part.",
        "slug: codes/fam",
        "---",
        "",
        f"**{len(sections):,} sections** · **{len(pages)} browsable pages** · **Snapshot updated by the source: November 27, 2025**",
        "",
        "The California Family Code is organized into Divisions and Parts. Each page below renders the full statutory text, section by section, with the legislative history for each section.",
        "",
        "<Note>",
        "The text is a dated research snapshot. Verify the current text, effective date, and applicability against the [official California Legislative Information](https://leginfo.legislature.ca.gov/faces/codes.xhtml) source before relying on a provision.",
        "</Note>",
        "",
    ]
    for (dnum, dtitle), entries in overview_by_div.items():
        ov += [f"## Division {esc(dnum)}. {esc(dtitle)}", ""]
        for label, href, first, last, n in entries:
            ov.append(f"- [{esc(label)}]({href}) — §§ {esc(first)}–{esc(last)} ({n} sections)")
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
    for (dnum, dtitle), entries in nav_by_div.items():
        div_label = json.dumps(f"Division {dnum}. {dtitle}", ensure_ascii=False)
        out.append(f"{ind}    - section: {div_label}")
        out.append(f"{ind}      contents:")
        for label, path in entries:
            out.append(f"{ind}        - page: {json.dumps(label, ensure_ascii=False)}")
            out.append(f"{ind}          path: {path}")
    print("\n".join(out))
    print(f"# {len(pages)} pages written", file=sys.stderr)


if __name__ == "__main__":
    main()
