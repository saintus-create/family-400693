# Workflow patch to generate full 162k MDX in CI

The branch `arena/01a0bc2b-family-400693` already contains:

- `scripts/generate_fern_sections_mdx.py` — generates one Fern MDX per statutory section
- `fern/docs.yml` — `folder: docs/pages/codes/sections` auto-discovers every `*.mdx`
- `fern/docs/pages/codes/sections/` — demo subset **FAM (1,636) + CONS (372) = 2,008 MDX** committed
- `fern/docs/pages/codes/mdx-transfer-guide.mdx` — full mapping from your other repos

To publish the **full 162,324-section** corpus on `legislature.docs.buildwithfern.com`, apply this patch to the 4 workflow files. The Arena GitHub App cannot push `/.github/workflows/*` without the `workflows` scope, so you must apply it from the GitHub UI (which has `workflows` permission) or by reconnecting the Arena app with workflows permission.

## What the patch does

Before `fern check` / `fern generate`, run:

```yaml
- name: Setup Python
  uses: actions/setup-python@v5
  with:
    python-version: "3.11"

- name: Generate per-section MDX (full corpus)
  run: python3 scripts/generate_fern_sections_mdx.py --clean
```

That regenerates `fern/docs/pages/codes/sections/` from `fern/docs/assets/corpus/law/*.jsonl.gz` on every run, so the repo can stay small (demo 2k) while the deployed site is complete (162k).

## Patch diff

```diff
diff --git a/.github/workflows/check.yml b/.github/workflows/check.yml
@@ -18,6 +18,14 @@ jobs:
         with:
           node-version: "24"

+      - name: Setup Python
+        uses: actions/setup-python@v5
+        with:
+          python-version: "3.11"
+
+      - name: Generate per-section MDX (full corpus)
+        run: python3 scripts/generate_fern_sections_mdx.py --clean
+
       - name: Setup Fern CLI
         uses: fern-api/setup-fern-cli@v1

diff --git a/.github/workflows/preview-docs.yml b/.github/workflows/preview-docs.yml
@@ -17,6 +17,14 @@ jobs:
         with:
           node-version: "24"

+      - name: Setup Python
+        uses: actions/setup-python@v5
+        with:
+          python-version: "3.11"
+
+      - name: Generate per-section MDX (full corpus)
+        run: python3 scripts/generate_fern_sections_mdx.py --clean
+
       - name: Setup Fern CLI
         uses: fern-api/setup-fern-cli@v1

diff --git a/.github/workflows/publish-docs.yml b/.github/workflows/publish-docs.yml
@@ -18,6 +18,14 @@ jobs:
         with:
           node-version: "24"

+      - name: Setup Python
+        uses: actions/setup-python@v5
+        with:
+          python-version: "3.11"
+
+      - name: Generate per-section MDX (full corpus)
+        run: python3 scripts/generate_fern_sections_mdx.py --clean
+
       - name: Setup Fern CLI
         uses: fern-api/setup-fern-cli@v1

diff --git a/.github/workflows/publish-fern.yml b/.github/workflows/publish-fern.yml
@@ -13,6 +13,14 @@ jobs:
       - name: Checkout repository
         uses: actions/checkout@v4

+      - name: Setup Python
+        uses: actions/setup-python@v5
+        with:
+          python-version: "3.11"
+
+      - name: Generate per-section MDX (full corpus)
+        run: python3 scripts/generate_fern_sections_mdx.py --clean
+
       - name: Install Fern CLI
         run: npm install -g fern-api@5.109.2
```

## How to apply (GitHub UI)

1. Open this repo on GitHub, switch to `arena/01a0bc2b-family-400693`.
2. Edit each file in `.github/workflows/` and insert the two steps above **right before** `Setup Fern CLI` / `Install Fern CLI` as shown.
3. Commit directly to the branch.

Or reconnect Arena with `workflows` permission and push again — `git push origin arena/01a0bc2b-family-400693` will then succeed with the workflow files included.

## Local full generation (no CI needed)

If you prefer to commit the full 162k MDX rather than generating in CI:

```bash
python3 scripts/generate_fern_sections_mdx.py --clean   # ~3 min, ~250 MB, 162k files
ls fern/docs/pages/codes/sections/fam | wc -l   # 1637
ls fern/docs/pages/codes/sections/cons | wc -l  # 373
git add fern/docs/pages/codes/sections
git commit -m "chore: commit full 162k MDX"
git push origin arena/01a0bc2b-family-400693   # may exceed patch limits; push in batches or keep CI approach
```

The raw patch is also at `/tmp/workflow.patch` in this workspace if you need to `git apply`.
