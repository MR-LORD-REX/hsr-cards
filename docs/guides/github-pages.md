# Publish with GitHub Pages

The documentation website is a static folder. It uses local HTML, CSS, JavaScript, Markdown content, and optimized card previews. There is no Node build, CDN dependency, or backend. All files required to display the site live inside `docs/`.

## Update the content

Edit the Markdown files under `docs/getting-started/`, `docs/guides/`, and `docs/api/`. `docs/readme.md` is the public index. Add demo metadata to `docs/data/showcase.json` through the rendering script.

From the repository root, build and validate the content bundle:

```bash
python scripts/build_docs.py
python scripts/validate_docs.py
```

The build produces `docs/data/content.js`. Commit that generated file with the Markdown sources when publishing from a branch. Validation checks public links, API coverage, code syntax, showcase files, and bundle freshness. It uses Python's standard library and does not contact providers.

## Preview locally

```bash
python -m http.server 8000 --directory docs
```

Open [localhost:8000](http://localhost:8000). Search, navigation, color themes, code copying, and card previews run in the browser. You can also open `docs/index.html` directly; the bundled content does not require Markdown fetch requests.

Routes use `#/page-id#heading`, for example [the endgame guide](../index.html#/guides/endgame). Markdown pages retain relative `.md` links so the same sources remain readable on GitHub. Site assets use relative paths, including when hosted under `/hsr-cards/`.

## Publish from a branch

1. Push the documentation and `Cards/showcase-*.png` originals to the repository.
2. Open the repository's **Settings → Pages**.
3. Select **Deploy from a branch**, choose `main`, and set the folder to **/docs**.
4. Save the setting and wait for GitHub's Pages build.

The expected URL is [mr-lord-rex.github.io/hsr-cards/](https://mr-lord-rex.github.io/hsr-cards/). The site is ready for this configuration; creating the files locally does not publish it.

## Publish through GitHub Actions

Alternatively, select **GitHub Actions** as the Pages source. The repository includes a [manual publication workflow](https://github.com/MR-LORD-REX/hsr-cards/blob/main/.github/workflows/docs-pages.yml).

Open **Actions → Publish documentation → Run workflow** when ready. It rebuilds and validates the Markdown bundle, then uploads only `docs/` to Pages. It has no push trigger. Use one Pages source configuration for the repository.

## Regenerate demo cards

```bash
python scripts/render_showcase.py --live-tiers
python scripts/build_docs.py
python scripts/validate_docs.py
```

The rendering script uses the library's public methods. It saves named PNG originals in `Cards/` and website previews in `docs/assets/showcase/`, then updates the manifest and Markdown gallery. Provider cache data and fictional player payloads are identified beside their outputs. Rendering needs the package dependencies and populated provider data/artwork caches. `--live-tiers` fetches all three public Prydwen rankings; omit it to use the local MOC parser fixture.

## Maintain the site

Keep `index.html`, `styles.css`, `app.js`, `assets/`, `data/`, and `.nojekyll` together. The `.nojekyll` file asks Pages to serve the static files directly. Review the gallery after regenerating examples, and rebuild the bundle whenever Markdown or showcase metadata changes.
