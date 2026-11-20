# Releasing a new version

Countertop uses version numbers like `v0.2.0`. Bump the last number for fixes, the middle one for new features.

1. Move the notes under **Unreleased** in [CHANGELOG.md](../CHANGELOG.md) into a new section, `## vX.Y.Z (date)`, written for the people who use Countertop.
2. Set `VERSION = "X.Y.Z"` near the top of [tools/countertop.py](../tools/countertop.py). Controls shows it, and it's how installs know an update is out.
3. Commit both to `main` and wait for the container check to pass.
4. Publish the release (from the repository folder, with the GitHub CLI):

   ```sh
   git pull
   gh release create vX.Y.Z --target main --title "Countertop vX.Y.Z" \
     --notes "$(python3 .github/release-notes.py vX.Y.Z)"
   ```

   `release-notes.py` stops with an error if `VERSION` and the changelog don't match the tag.

Publishing the release starts the **Countertop container** workflow. It checks the version again, runs the smoke test on amd64 and arm64, and pushes `ghcr.io/kizit/countertop:vX.Y.Z` and `:latest`. Unraid's **Check for Updates** and `docker compose pull` pick up `:latest`, and within 12 hours every install's Controls shows the update notice with a link to the release notes.
