# CA Leg Info

A documentation site for California legislative research, built with [Fern](https://buildwithfern.com) and published at [legislature.docs.buildwithfern.com](https://legislature.docs.buildwithfern.com).

The site contains the **full statutory text of the California Constitution and all 29 statutory codes** (162,324 sections):

- **Code pages** — every code is browsable end to end, split at its official division boundaries (one page for small codes).
- **Corpus search** — a client-side search at `/codes/search` that streams one compressed code at a time and ranks matches by citation and text.
- **Ask Fern AI** — the same snapshot is indexed into the site's AI assistant (see `scripts/sync_fern_legal_corpus.py`).
- **Bulk data** — `fern/assets/corpus/law/*.jsonl.gz` plus a `manifest.json` with checksums and provenance.

> The corpus is a dated research snapshot, not legal advice. Verify current text and effective dates at the [official California Legislative Information portal](https://leginfo.legislature.ca.gov/).

## Repository layout

```
fern/
  fern.config.json           # Fern org + CLI version
  docs.yml                   # site config + explicit navigation (every page listed)
  custom.js                  # corpus search + landing hero
  assets/                    # logos, favicon, styles, corpus (jsonl.gz + manifest)
  pages/                     # all MDX pages
    welcome.mdx              # landing page
    codes/<code>.mdx         # per-code overview (stats, downloads, contents)
    codes/<code>/*.mdx       # per-code full statutory text (division-chunked)
    changelog/               # release notes (Changelog tab)
scripts/
  generate_code_pages.py     # regenerate all code pages + nav data from the corpus
  sync_fern_legal_corpus.py  # index corpus into Fern Ask AI (Documents API)
```

## Development

```bash
npm install -g fern-api
fern check     # validate configuration
fern generate --docs --local  # local build (requires a Fern token)
```

## CI/CD (GitHub Actions)

- **check.yml** — validates the Fern configuration on every PR and push to `main`.
- **preview-docs.yml** — publishes a preview URL and comments it on the PR.
- **publish-docs.yml** — on push to `main`: publishes to `legislature.docs.buildwithfern.com`. Requires the `FERN_TOKEN` secret.

## Regenerating code pages

```bash
python3 scripts/generate_code_pages.py
```

Rebuilds every code page from the compressed corpus in `fern/assets/corpus/` and emits `code-nav.json`, the navigation data mirrored into `fern/docs.yml`. Pages are packed to stay under ~4 MB so builds and browsers stay fast.
