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

    # Size-driven splitting: Division -> Part -> Chapter -> Article -> batches
    # of sections, until every page is under MAX_CHARS.
    MAX_CHARS = 300_000
    LEVELS = ["part", "chapter", "article"]

    def size(secs):
        return sum(len(s.get("text") or "") + len(s.get("history") or "") + 40 for s in secs)

    groups = OrderedDict()
    for s in sections:
        groups.setdefault(s["division"], []).append(s)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for old in OUT_DIR.glob("*.mdx"):
        old.unlink()

    nav_by_div = OrderedDict()      # (dnum, dtitle) -> path or [(label, path)]
    overview_by_div = OrderedDict() # (dnum, dtitle) -> [(label|None, href, first, last, n)]
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
            for lvl, reset in (("part", ("chapter", "article")), ("chapter", ("article",)), ("article", ())):
                if s[lvl] != cur[lvl]:
                    cur[lvl] = s[lvl]
                    for r in reset:
                        cur[r] = object()
                    if cur[lvl] and lvl in top_level:
                        n, t = split_label(cur[lvl])
                        name = lvl.capitalize()
                        idx = top_level.index(lvl)
                        if idx == 0:
                            lines += [f"## {name} {esc(n)}. {esc(t)}", ""]
                        elif idx == 1:
                            lines += [f"**{name} {esc(n)}. {esc(t)}**", ""]
                        else:
                            lines += [f"*{name} {esc(n)}. {esc(t)}*", ""]
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
        body = "\n".join(lines).rstrip() + "\n"
        (OUT_DIR / fname).write_text(body, encoding="utf-8")
        pages.append(fname)
        return first, last

    def emit(secs, dnum, dtitle, crumbs, slug_parts, level_idx, results):
        """Write secs as one page if small enough, else split at the next level."""
        if size(secs) <= MAX_CHARS or level_idx > len(LEVELS):
            if level_idx > len(LEVELS) and size(secs) > MAX_CHARS:
                # Fallback: fixed batches of sections.
                batch, n = [], 1
                for s in secs:
                    batch.append(s)
                    if size(batch) > MAX_CHARS * 0.9:
                        emit(batch, dnum, dtitle, crumbs + [f"Sections {batch[0]['section']}–{batch[-1]['section']}"],
                             slug_parts + [f"sections-{slug_num(batch[0]['section'])}"], len(LEVELS) + 1, results)
                        batch = []
                if batch:
                    emit(batch, dnum, dtitle, crumbs + [f"Sections {batch[0]['section']}–{batch[-1]['section']}"],
                         slug_parts + [f"sections-{slug_num(batch[0]['section'])}"], len(LEVELS) + 1, results)
                return
            fname = "-".join(slug_parts) + ".mdx"
            slug = "codes/fam/" + "-".join(slug_parts)
            title = f"Division {dnum}. {dtitle}" if len(crumbs) == 1 else f"Division {dnum}, " + ", ".join(crumbs[1:])
            desc = f"California Family Code {' › '.join(crumbs)} — sections {secs[0]['section']} to {secs[-1]['section']}, {len(secs)} sections with full text."
            crumb = "California Family Code · " + " › ".join(esc(c) for c in crumbs)
            remaining = LEVELS[min(level_idx, len(LEVELS)):]
            first, last = write_page(fname, slug, title, desc, crumb, secs, remaining)
            label = None if len(crumbs) == 1 else ", ".join(crumbs[1:])
            results.append((label, fname, f"/{slug}", first, last, len(secs)))
            return
        lvl = LEVELS[level_idx]
        if not any(s[lvl] for s in secs):
            emit(secs, dnum, dtitle, crumbs, slug_parts, level_idx + 1, results)
            return
        sub = OrderedDict()
        for s in secs:
            sub.setdefault(s[lvl], []).append(s)
        for label, ssecs in sub.items():
            if label is None:
                emit(ssecs, dnum, dtitle, crumbs, slug_parts, level_idx + 1, results)
                continue
            n, t = split_label(label)
            emit(ssecs, dnum, dtitle, crumbs + [f"{lvl.capitalize()} {n}. {t}"],
                 slug_parts + [lvl, slug_num(n)], level_idx + 1, results)

    for div, secs in groups.items():
        dnum, dtitle = split_label(div)
        key = (dnum, dtitle)
        results = []
        emit(secs, dnum, dtitle, [f"Division {dnum}. {dtitle}"], ["division", slug_num(dnum)], 0, results)
        if len(results) == 1 and results[0][0] is None:
            _, fname, href, first, last, n = results[0]
            nav_by_div[key] = f"docs/pages/codes/fam/{fname}"
            overview_by_div[key] = [(None, href, first, last, n)]
        else:
            nav_by_div[key] = [(label or f"Division {dnum}", f"docs/pages/codes/fam/{fname}") for label, fname, *_ in results]
            overview_by_div[key] = [(label or f"Division {dnum}", href, first, last, n) for label, fname, href, first, last, n in results]

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
        "The California Family Code is organized into Divisions, rendered one page per Division below (large Divisions are split by Part, Chapter, or Article to keep pages readable), with the full statutory text, section by section, with the legislative history for each section.",
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
