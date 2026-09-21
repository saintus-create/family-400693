#!/usr/bin/env python3
"""Generate LegInfo-style code pages for the CA Leg Info Fern site.

Reads the compressed corpus (fern/assets/corpus) and emits:
  - fern/pages/codes/<code>.mdx          overview + table of contents
  - fern/pages/codes/<code>/<unit>.mdx   full statutory text, chunked
  - code-nav.json                        navigation data for docs.yml assembly

Pages are packed to stay under CAP characters so Fern's MDX compiler and
browsers stay comfortable. Sibling units are merged greedily; oversized
units are subdivided at the next hierarchy level.
"""
import gzip
import json
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
CORPUS = REPO / "fern/assets/corpus"
PAGES_DIR = REPO / "fern/pages/codes"
CAP = 4_000_000

CODE_NAMES = {
    "CONS": "California Constitution", "BPC": "Business and Professions Code",
    "CIV": "Civil Code", "CCP": "Code of Civil Procedure", "COM": "Commercial Code",
    "CORP": "Corporations Code", "EDC": "Education Code", "ELEC": "Elections Code",
    "EVID": "Evidence Code", "FAM": "Family Code", "FIN": "Financial Code",
    "FGC": "Fish and Game Code", "FAC": "Food and Agricultural Code", "GOV": "Government Code",
    "HNC": "Harbors and Navigation Code", "HSC": "Health and Safety Code",
    "INS": "Insurance Code", "LAB": "Labor Code", "MVC": "Military and Veterans Code",
    "PEN": "Penal Code", "PROB": "Probate Code", "PCC": "Public Contract Code",
    "PRC": "Public Resources Code", "PUC": "Public Utilities Code",
    "RTC": "Revenue and Taxation Code", "SHC": "Streets and Highways Code",
    "UIC": "Unemployment Insurance Code", "VEH": "Vehicle Code", "WAT": "Water Code",
    "WIC": "Welfare and Institutions Code",
}
SLUG_FOR = {"division": "div", "part": "part", "title": "title", "chapter": "ch", "article": "art"}
AMP = chr(38)


def esc(text):
    text = text.replace(AMP, AMP + "amp;")
    text = text.replace("<", AMP + "lt;")
    text = text.replace("{", AMP + "#123;")
    text = text.replace("}", AMP + "#125;")
    return text


def yq(value):
    return json.dumps(value, ensure_ascii=False)


class Node:
    def __init__(self, kind, number, title, path):
        self.kind, self.number, self.title, self.path = kind, number, title, path
        self.children, self.sections = [], []
        self.parent = None

    @property
    def label(self):
        return f"{self.kind.capitalize()} {self.number}. {self.title}".rstrip(". ")

    @property
    def slug_chain(self):
        chain = []
        node = self
        while node is not None and node.kind != "__root__":
            chain.append(f"{SLUG_FOR.get(node.kind, node.kind)}-{str(node.number).lower().replace(' ', '-')}")
            node = node.parent
        return list(reversed(chain))

    @property
    def size(self):
        return sum(len(s.get("text") or "") for s in self.sections) + sum(c.size for c in self.children)

    @property
    def all_sections(self):
        for s in self.sections:
            yield s
        for c in self.children:
            yield from c.all_sections


def build_tree(records):
    nodes, roots = {}, []
    for r in records:
        if r["kind"] == "section":
            continue
        path = r.get("path") or f"{r['kind']} {r.get('number', '')}"
        node = Node(r["kind"], r.get("number", ""), r.get("title", ""), path)
        nodes[path] = node
        parent_key = " > ".join(path.split(" > ")[:-1])
        parent = nodes.get(parent_key) if parent_key else None
        if parent is not None:
            node.parent = parent
            parent.children.append(node)
        else:
            roots.append(node)
    for r in records:
        if r["kind"] == "section":
            node = nodes.get(r.get("path") or "")
            if node is None:
                node = roots[0] if roots else None
            if node is not None:
                node.sections.append(r)
    return roots


def pack(nodes, cap=CAP):
    buckets, current, total = [], [], 0
    for n in nodes:
        s = n.size
        if current and total + s > cap:
            buckets.append(current)
            current, total = [], 0
        current.append(n)
        total += s
    if current:
        buckets.append(current)
    return buckets


def emit_page(code, code_name, units, context=None, part_no=None, hard_sections=None):
    code_dir = PAGES_DIR / code.lower()
    code_dir.mkdir(parents=True, exist_ok=True)
    first, last = units[0], units[-1]
    slug_bits = first.slug_chain
    slug = "-".join(slug_bits[-1:] + ([last.slug_chain[-1]] if len(units) > 1 else []))
    # full unique slug = ancestor chain of first unit + first/last unit slugs
    ancestors = slug_bits[:-1]
    if len(units) > 1:
        leaf = f"{first.slug_chain[-1]}-{last.slug_chain[-1]}"
    else:
        leaf = first.slug_chain[-1]
    full_slug = "/".join(ancestors + [leaf])
    if part_no:
        full_slug += f"-p{part_no}"

    ctx = f"{context} — " if context else ""
    if len(units) == 1:
        title = f"{code_name}: {ctx}{first.label}"
    else:
        title = f"{code_name}: {ctx}{first.kind.capitalize()} {first.number}–{last.number}"

    secs = hard_sections if hard_sections is not None else list(first.all_sections)
    sec_ids = [s.get("section") for s in secs if s.get("section")]
    lo = min(sec_ids, key=lambda x: (len(x), x), default="")
    hi = max(sec_ids, key=lambda x: (len(x), x), default="")
    desc = f"California {code_name}, {ctx}{first.label}" + (f" — §§ {lo}–{hi}" if lo else "") + ". Full statutory text."

    out = [
        f"---\ntitle: {yq(title)}\ndescription: {yq(desc)}\nslug: {yq(f'codes/{code.lower()}/{full_slug}')}\n---\n",
        f"# {esc(title)}\n",
        f"[← {esc(code_name)} overview](/codes/{code.lower()}) · [Search the corpus](/codes/search)\n",
        "<Note>\nDated research snapshot. Verify current text and effective dates at the "
        "[official California Legislative Information source](https://leginfo.legislature.ca.gov/faces/codes.xhtml).\n</Note>\n",
    ]

    min_depth = min(depth_of(u) for u in units)

    def render_section(s):
        citation = s.get("citation") or f"{code} § {s.get('section')}"
        repealed = " *(Repealed)*" if s.get("repealed") else ""
        out.append(f"\n**{esc(citation)}**{repealed}\n")
        text = (s.get("text") or "").strip()
        if text:
            out.append(esc(text) + "\n")
        history = (s.get("history") or "").strip()
        if history:
            out.append(f"*{esc(history)}*\n")

    def render_unit(unit, depth):
        level = min(2 + depth - min_depth, 6)
        out.append(f"\n{'#' * level} {esc(unit.label)}\n")
        for s in unit.sections:
            render_section(s)
        for c in unit.children:
            render_unit(c, depth + 1)

    if hard_sections is not None:
        for s in hard_sections:
            render_section(s)
    else:
        for u in units:
            render_unit(u, depth_of(u))

    (code_dir / f"{leaf}{f'-p{part_no}' if part_no else ''}.mdx").write_text("\n".join(out), encoding="utf-8")
    return {"slug": f"codes/{code.lower()}/{full_slug}", "title": title,
            "path": f"pages/codes/{code.lower()}/{leaf}{f'-p{part_no}' if part_no else ''}.mdx",
            "sections": len(secs)}


def depth_of(node):
    return node.path.count(" > ")


def emit_units(code, code_name, units, context=None):
    entries = []
    for bucket in pack(units):
        if len(bucket) == 1 and bucket[0].size > CAP:
            unit = bucket[0]
            ctx = f"{context} — {unit.label}" if context else unit.label
            if unit.children:
                entries.extend(emit_units(code, code_name, unit.children, ctx))
            else:
                sections = list(unit.all_sections)
                n = (unit.size // CAP) + 1
                per = len(sections) // n + 1
                parts = [sections[i:i + per] for i in range(0, len(sections), per)]
                for i, p in enumerate(parts, 1):
                    entries.append(emit_page(code, code_name, [unit], context, i, p))
        else:
            entries.append(emit_page(code, code_name, bucket, context))
    return entries


def main():
    manifest = json.loads((CORPUS / "manifest.json").read_text())
    nav = []
    total_pages = 0
    for ds in manifest["datasets"]:
        code, code_name = ds["abbr"], CODE_NAMES[ds["abbr"]]
        records = [json.loads(l) for l in gzip.open(CORPUS / ds["file"], "rt", encoding="utf-8") if l.strip()]
        records.sort(key=lambda r: r.get("ordinal", 0))
        roots = build_tree(records)
        entries = emit_units(code, code_name, roots)
        total_pages += len(entries) + 1
        nav.append({"code": code, "name": code_name, "slug": f"codes/{ds['slug']}",
                    "sections": ds["sections"], "updated": ds["updated_by_state"],
                    "entries": entries})

        toc = "\n".join(f"- [{esc(e['title'])}](/{e['slug']})" for e in entries) or "- See below"
        overview = f"""---
title: {yq(code_name)}
description: {yq(f"Complete text of the California {code_name} — {ds['sections']:,} sections, organized by official divisions.")}
slug: {yq(f"codes/{ds['slug']}")}
---

# {esc(code_name)}

**{ds['sections']:,} sections** · **Snapshot updated by the source: {ds['updated_by_state']}**

The complete statutory text of the {esc(code_name)}, organized by its official
divisions. Locate sections with the [corpus search](/codes/search), or ask **Ask AI**,
which is indexed against this same snapshot.

## Contents

{toc}

## Downloads

- [Download the `{code}.jsonl.gz` dataset](https://github.com/saintus-create/family-400693/blob/main/fern/assets/corpus/law/{code}.jsonl.gz)
- [Download the corpus manifest](https://github.com/saintus-create/family-400693/blob/main/fern/assets/corpus/manifest.json)
- [Browse the official California code search](https://leginfo.legislature.ca.gov/faces/codes.xhtml)

<Note>
Dated research snapshot. Verify current text, effective dates, and applicability against the
[official California Legislative Information source](https://leginfo.legislature.ca.gov/faces/codes.xhtml)
before relying on a provision.
</Note>
"""
        (PAGES_DIR / f"{ds['slug']}.mdx").write_text(overview, encoding="utf-8")
        print(f"{code:<5} {ds['sections']:>6,} sections -> {len(entries)} page(s)")

    (REPO / "code-nav.json").write_text(json.dumps(nav, indent=1))
    print(f"TOTAL: {total_pages} pages (incl. overviews)")


if __name__ == "__main__":
    main()
