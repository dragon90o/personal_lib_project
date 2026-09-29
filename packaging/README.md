# Packaging

What `.github/workflows/release.yml` needs to build the downloadable program.
Nothing here is used when running from source.

- `msix/` — the Microsoft Store package: `AppxManifest.xml` (its `@VERSION@`
  is filled in from the git tag, `v1.2.0` → `1.2.0.0`) and the tile icons in
  `Assets/`, made from `assets/readaloud-1024.png`.
- `linux/` — the AppImage: `AppRun` (starts the program) and
  `readaloud.desktop` (its entry in the application menu).

## Releasing a new version

One tag builds both systems, so they never drift apart:

    git tag v1.2.0
    git push origin v1.2.0

The workflow builds the Windows `.msix` and the Linux `.AppImage` and attaches
both to one GitHub Release. If either build fails, nothing is published.

The `.msix` still has to be uploaded to Partner Center by hand (Microsoft signs
it there): download it from the Release and submit it as a new package.
