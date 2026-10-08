# Releasing carculator_truck 0.5.1

Status: prepared, not published. Use Python 3.12 and review the matching family set:

| Package | Prepared version |
| --- | --- |
| `carculator_utils` | 1.3.6 |
| `carculator` | 1.9.6 |
| `carculator_truck` | 0.5.1 |
| `carculator_bus` | 0.1.1 |
| `carculator_two_wheeler` | 0.1.1 |


1. Review `CHANGELOG.md`, known limitations in `docs/validity.rst`, and the worktree.
   Preserve local notebooks and inventories; commit only the intended release files.
2. Check `carculator_truck/_version.py`, `conda/meta.yaml` and dependency metadata together.
   Sphinx reads the package version automatically. All vehicle packages require
   `carculator_utils>=1.3.6`, including the optional export extras.
3. Build and verify actual artifacts from this checkout (use a new output directory):

```bash
python ../carculator_utils/scripts/verify_installation.py --repositories ../carculator_utils . --output /tmp/carculator_truck-release-check --run-tests
```

For the complete family, run from `carculator_utils`:

```bash
python scripts/verify_installation.py \
  --repositories . ../carculator ../carculator_truck ../carculator_bus ../carculator_two_wheeler \
  --output /tmp/carculator-family-release-check --run-tests
```

The verifier builds wheels and sdists, rebuilds wheels from sdists, compares
packaged resource hashes, runs installed tests with export extras and checks
offline core-only model/LCIA runs. Keep `report.json`, test XML, dependency freezes
and artifact hashes with the release record. A local pass does not establish
that Linux, Windows or hosted CI passed. Confirm the release commit's CI separately.

4. Install `.[docs]`, build with `python -m sphinx -b html docs docs/_build/html`,
   and run the README example. Check wheel/sdist metadata before publication:

```bash
python -m pip install twine
python -m twine check --strict /tmp/carculator-family-release-check/wheels/carculator_truck-0.5.1-py3-none-any.whl /tmp/carculator-family-release-check/wheels/carculator_truck-0.5.1.tar.gz
```

5. Publish `carculator_utils` **first** and confirm that 1.3.6 is available before
   publishing the four vehicle packages. The same ordering applies to conda.
   Replace `Unreleased` with the actual publication date in the changelog, commit
   the final release metadata, and verify the final artifacts. Create an annotated
   `v.0.5.1` tag on that reviewed commit, following existing tag conventions.
   Do not reuse an existing tag or upload a different build under the same version.
6. Publish the GitHub release for the reviewed tag. The `main.yml` workflow
   verifies installed artifacts on Linux, macOS, and Windows before uploading the
   exact verified wheel and sdist to PyPI using the existing `PYPI_PASSWORD` secret.
   Tags `v.X.Y.Z` and `vX.Y.Z` are accepted; the tag, package version, and conda
   recipe version must match. Attach the verification record to the release.
7. The workflow also builds and tests the matching noarch conda package, then
   uploads it to the `romainsacchi` channel using `ANACONDA_CLOUD`. Required
   dependencies must already be available in the configured conda channels.

To publish an existing tag after this workflow reaches the default branch, run
**Actions → Installed artifacts and release publishing → Run workflow** on that
branch and enter the tag in `release_tag`. The workflow checks out and verifies
that tag before publishing; an empty input only verifies. Existing registry files
are skipped on reruns. Ordinary pushes and pull requests only run verification;
creating a tag alone does not publish. Publish its GitHub release instead.


The prepared metadata and README examples target this release; older published
packages may not provide the documented APIs or 2025 defaults.
