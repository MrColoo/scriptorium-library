# Releasing

A release is one annotated tag. Pushing it starts the **Release** workflow
(`.github/workflows/release.yml`), which checks the release notes, runs the tests, builds and pushes
the image and writes the GitHub release. Nobody builds or uploads anything by hand.

The release notes in `cps/release_notes.json` are the single source of truth. The same entry is
shown in the app (the update dialog before updating, *What's new* after) and becomes the GitHub
release text.

## Versions

[Semantic versioning](https://semver.org): `vMAJOR.MINOR.PATCH`.

- **Patch** (`v1.1.1`): fixes only.
- **Minor** (`v1.2.0`): new features; existing setups keep working.
- **Major** (`v2.0.0`): something users must act on, explained in the release notes.
- **Pre-release** (`v1.2.0-rc.1`): published for testing. It is not marked as the latest release,
  does not move the `latest`, `v1` or `v1.2` image tags, and the app does not offer it as an update.

## Steps

1. **Write the notes** while the work lands on `main`:

   ```bash
   python3 scripts/release.py new v1.2.0
   ```

   This adds an entry with `TODO`s to `cps/release_notes.json`. Fill in, in English and Italian:
   a title, one to six highlights (each with an `icon` from `cps/static/img/icons.svg`), and a
   `quote`: a short line from a book that fits the release, with author and book. Prefer
   public-domain works, and keep it to a sentence.

2. **Check and preview** it:

   ```bash
   python3 scripts/release.py check v1.2.0
   python3 scripts/release.py prepare v1.2.0 --dry-run
   ```

   `check` lists anything missing; `--dry-run` prints the GitHub release text and changes nothing.

3. **Prepare** the release from a clean `main`:

   ```bash
   python3 scripts/release.py prepare v1.2.0
   ```

   It refuses to run on another branch, with uncommitted changes, for an existing tag or for a
   version that is not newer than the latest release. Otherwise it sets the date in the notes,
   commits `Release v1.2.0` and creates the annotated tag. It does not push.

4. **Publish**:

   ```bash
   git push origin main
   git push origin v1.2.0
   ```

5. **Follow** the run under *Actions → Release*. Most of the time goes into building the arm64
   image under emulation. When it finishes:

   - the image is at `ghcr.io/mrcoloo/scriptorium-library` as `v1.2.0`, `v1.2`, `v1` and `latest`,
     for `linux/amd64` and `linux/arm64`, with an SBOM and signed build provenance;
   - the GitHub release *Scriptorium v1.2.0* has the highlights, the quote, the update command,
     an Italian version and the list of merged changes;
   - running installs see the update button within twelve hours (or at their next restart).

## What the workflow does

| Job | What it does |
| --- | --- |
| Check tag and release notes | Rejects malformed tags and incomplete notes before anything is built, and renders the release text. |
| Fast tests | The same smoke and unit tests as every push, on the tagged commit. |
| Build and push the image | Multi-arch build with the version baked in (`VERSION`), OCI labels pointing at the tagged commit, SBOM and provenance attestation. |
| Publish the GitHub release | Creates the release (or updates it if it exists, for example a draft), marks it latest unless it is a pre-release. |

Each job gets only the permissions it needs: reading the repository, plus writing packages for the
image job and writing contents for the release job.

You can check where an image came from with the GitHub CLI:

```bash
gh attestation verify oci://ghcr.io/mrcoloo/scriptorium-library:v1.2.0 --owner MrColoo
```

## Re-running for an existing tag

*Actions → Release → Run workflow* takes a tag that already exists. Leave **Test, build and push
the Docker image** on to rebuild the image (for example after a base-image security fix), or turn it
off to only write or refresh the GitHub release. Release notes for older tags are read from `main`
when the tag itself has none.

## If a release goes wrong

Never move or reuse a published tag: people may already run that image. Fix the problem on `main`
and release the next patch version. If the GitHub release text is wrong, correct the notes on
`main` and re-run the workflow for that tag with the image build turned off.
