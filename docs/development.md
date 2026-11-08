# Development and maintenance

[← HLSync README](../README.md)

Install the development environment and run the test suite:

```console
python -m pip install -e '.[dev]'
pytest
```

## Switching the installed `hlsync`

To test unpublished changes with your installed `hlsync` command, switch it to
your checkout. Run this from the repository root:

```console
uv tool install --force --editable .
```

The command then runs the checkout's code, so edits take effect without
reinstalling. `hlsync --version` is computed from Git history when you install;
rerun the command after committing to refresh it. Use `hlsync --legend` for a
quick display check, or run `hlsync diff` from a mapped project to preview its
differences.

To switch back to the published release from PyPI:

```console
uv tool install --force hlsync
```

## Project layout

The PyPI distribution, installed command, and Python package are all `hlsync`.
See [`TODO.md`](../TODO.md) for the ordered work queue and [`CHANGELOG.md`](../CHANGELOG.md) for completed changes.
[`decisions/`](../decisions/) holds substantial architectural choices and their
rationale. CLI conventions and current usage are documented in the README and
`docs/`; smaller changes are explained in commit messages.

The self-contained PHP 8.3 project site is in [`website/`](../website/README.md).

## Releasing to PyPI

Releases use `<major>.<work-day>.<increment>` without leading zeroes. Versions
advance from a starting version using Git history, not the build date:

- [`version.json`](../version.json) assigns a starting version to a baseline
  commit. The empty root commit starts the counter at `1.16.2`; the first
  source snapshot is `1.16.3`, continuing the version 1 release sequence.
- Each subsequent date with commits advances the starting work-day number
  by one, regardless of how many idle days pass.
- On the baseline day, the increment advances from its starting value for
  each later commit. On subsequent work days, it starts at `1` and counts
  commits on that date.
- Dates use each commit's recorded committer date and timezone. Only the
  first-parent history of the current checkout counts; a merge counts once.
  All commits count, including documentation and maintenance changes.

The first source snapshot is `1.16.3`. Another commit on the same date is
`1.16.4`. The next date with a commit produces `1.17.1`, even after a week
without changes.

Builds require history back to the baseline and reject backwards-moving commit
dates. Wheels and source archives preserve the computed version; installed
commands do not access Git. Reinstall editable checkouts after committing to
refresh their installed version. To select a new baseline, update `version.json`
with its starting `version` and an existing `commit` on the same first-parent
history. To start a new major, use `<major>.0.1` as its starting version.
Keep the baseline fixed between releases; ordinary commits advance the version.

Use an existing PyPI account with two-factor authentication and an API token.
Twine uses credentials from `~/.pypirc` or `TWINE_USERNAME`/`TWINE_PASSWORD`,
and prompts if needed. Do not store the token in the repository.

1. Commit the changes to release. Use a checkout with history back to the
   baseline in `version.json`. Do not edit the generated `_version.py`.
2. Update [`CHANGELOG.md`](../CHANGELOG.md) when useful. Release notes and dated
   headings are optional and do not block publishing.
3. Commit any release-note changes. From that clean checkout, with development
   dependencies installed, run:

   ```console
   ./scripts/publish.sh
   ```

   The script uses the repository's `.venv/bin/python` when available, otherwise
   `python3`; set `PYTHON` to select another interpreter. It builds through
   helpers in `scripts/helpers/`, which run identity checks, lint, tests, isolated builds,
   metadata checks, and a clean wheel installation, then uploads both artifacts.
   If `dist/hlsync/<version>/` already exists, it reuses those prepared artifacts after
   checking their metadata. New commits advance the version;
   existing artifacts are not rebuilt automatically.

   To prepare artifacts without publishing, run `./scripts/publish.sh --prepare`.

4. A Git tag is not required by PyPI. It is strongly recommended for source
   provenance: tag the release commit as `v<version>`, push that tag, and create
   a corresponding GitHub Release.
5. Install the published version in a clean environment and run `hlsync --version`
   before announcing it.

PyPI does not allow a published version to be replaced. If publication fails
after accepting either artifact, create another commit (an empty release-retry
commit is sufficient) and build a new release; do not reuse the failed version.
Publish from one release history: separate branches can compute the same
version and are not separate publication streams.
