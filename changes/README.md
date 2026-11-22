# Notes for the next release

Each pull request that changes something people will notice adds one small file here, instead of editing `CHANGELOG.md`. Separate files never conflict, so any number of pull requests can be open at once.

- `new/` for something people can now do
- `changed/` for something that works differently
- `fixed/` for something that was broken

Name the file after the change (for example `new/portrait-displays.md`) and write one line in it, starting with `- `, for the people who use Countertop:

```markdown
- **Portrait displays.** The dashboard arranges your boxes into rows on tall screens.
```

When a release is published, these notes become its section in [CHANGELOG.md](../CHANGELOG.md) and the release notes, and the files are removed. See [releasing](../docs/releasing.md).

## A story for a bigger release

For a release worth showing off, add `release-story.md` here: a plain-language introduction with screenshots or GIFs, in Markdown. The release puts it at the top of the release notes, with the generated notes below under "What's changed", and removes the file. It is not added to the changelog. Without the file, the release notes are just the generated ones.
