# CA Leg Info

Documentation for **CA Leg Info**, a curated starting point for navigating California legislative, judicial, and public-record information.

The site is built with [Fern](https://buildwithfern.com/) and keeps the homepage in `fern/docs/pages/welcome.mdx`. The homepage is intentionally preserved as a custom landing page; supporting destinations live alongside it as ordinary MDX pages.

The repository now includes a Fern-compatible package of the complete California law snapshot from [`assistant-ui-template-for-law`](https://github.com/saintus-create/assistant-ui-template-for-law): 29 statutory codes plus the California Constitution, totaling 162,324 sections. The compressed section-level datasets live under `fern/docs/assets/corpus/` and are indexed by `fern/docs/assets/corpus/manifest.json`.

## Repository layout

| Path | Purpose |
| --- | --- |
| `fern/docs/pages/` | Human-authored documentation pages |
| `fern/docs/assets/corpus/` | Compressed section datasets and corpus manifest |
| `fern/docs.yml` | Navigation, branding, and site configuration |
| `fern/styles.css` | Site-wide visual system and accessible focus states |
| `fern/custom.js` | Site-wide client-side behavior |
| `fern/openapi.yaml` | Existing OpenAPI reference source |
| `fern/asyncapi.yaml` | Existing AsyncAPI reference source |
| `.github/workflows/` | Automated validation and publishing workflows |

## Local development

Install the [Fern CLI](https://buildwithfern.com/learn/docs/cli/cli-overview), then run:

```bash
fern check
fern docs dev
```

`fern check` is the required pre-commit validation. The GitHub Actions check runs it for pull requests and pushes to `main`.

To rebuild the Fern package from a checkout of the corpus repository:

```bash
python3 scripts/build_fern_corpus.py /path/to/assistant-ui-template-for-law .
```

The converter copies the canonical `.jsonl.gz` snapshots, verifies that all 30 datasets are present, writes the manifest, and generates one lightweight catalog page per code. It does not create one MDX page per section.

## Content guidelines

- Prefer first-party California sources for links and citations.
- Include the access date when recording time-sensitive research.
- Distinguish proposed legislation, enacted statutes, operative provisions, and court opinions.
- Do not present general information as legal advice.
- Preserve the homepage and existing API source files unless a deliberate content migration is requested.

## Scope

CA Leg Info is an information and navigation resource. It does not provide legal advice, form an attorney-client relationship, or guarantee that linked material is current or complete.
