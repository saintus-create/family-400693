# CA Leg Info

Documentation for **CA Leg Info**, a curated starting point for navigating California legislative, judicial, and public-record information.

The site is built with [Fern](https://buildwithfern.com/) and keeps the homepage in `fern/docs/pages/welcome.mdx`. The homepage is intentionally preserved as a custom landing page; supporting destinations live alongside it as ordinary MDX pages.

## Repository layout

| Path | Purpose |
| --- | --- |
| `fern/docs/pages/` | Human-authored documentation pages |
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

## Content guidelines

- Prefer first-party California sources for links and citations.
- Include the access date when recording time-sensitive research.
- Distinguish proposed legislation, enacted statutes, operative provisions, and court opinions.
- Do not present general information as legal advice.
- Preserve the homepage and existing API source files unless a deliberate content migration is requested.

## Scope

CA Leg Info is an information and navigation resource. It does not provide legal advice, form an attorney-client relationship, or guarantee that linked material is current or complete.
