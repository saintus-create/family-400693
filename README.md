# CA Leg Info

A documentation site for California legislative research, built with [Fern](https://buildwithfern.com) and published at [legislature.docs.buildwithfern.com](https://legislature.docs.buildwithfern.com).

The site packages a **section-level snapshot of the California Constitution and all 29 statutory codes** (162,324 sections) as:

- **Catalog pages** — a lightweight overview per code, with dataset download links.
- **Corpus search** — a client-side search at `/codes/search` that streams one compressed code at a time and ranks matches by citation and text.
- **Ask Fern AI** — the same snapshot is indexed into the site's AI assistant (see `scripts/sync_fern_legal_corpus.py`).
- **Bulk data** — `fern/docs/assets/corpus/law/*.jsonl.gz` plus a `manifest.json` with checksums and provenance.

> The corpus is a dated research snapshot, not legal advice. Verify current text and effective dates at the [official California Legislative Information portal](https://leginfo.legislature.ca.gov/).

## Repository layout

```
fern/
  docs.yml                     # navigation, tabs, theming, AI system prompt
  custom.js                    # landing hero + corpus search (streams .jsonl.gz)
  landing-hero.js              # hero interactions (Ask AI, ⌘K)
  styles.css                   # site styling
  docs/
    pages/                     # MDX pages (landing, codes catalog, research)
    assets/corpus/              # compressed datasets + manifest
    changelog/                  # release notes rendered in the Changelog tab
scripts/
  build_fern_corpus.py         # regenerate catalog pages + corpus assets
  generate_fern_sections_mdx.py # optional: one MDX per statutory section (offline)
  sync_fern_legal_corpus.py    # index corpus into Fern Ask AI (Documents API)
```

## Development

Install the Fern CLI (`npm install -g fern-api`), then:

```bash
fern check          # validate configuration
fern generate --docs --local  # build locally (requires a Fern token)
```

## CI/CD (GitHub Actions)

- **check.yml** — validates the Fern configuration on every PR and push to `main`.
- **preview-docs.yml** — publishes a preview URL and comments it on the PR.
- **publish-fern.yml** — on push to `main`: validates, publishes to `legislature.docs.buildwithfern.com`, and re-indexes the corpus for Ask Fern. Requires the `FERN_TOKEN` secret.

## Regenerating the corpus

```bash
python3 scripts/build_fern_corpus.py /path/to/source/checkout
```

This rebuilds the catalog pages and the compressed `jsonl.gz` assets from the canonical `data/law/*.jsonl.gz` snapshot, then updates `manifest.json`.
