# Release Policy

This repository uses semantic versioning and maintains a stable main branch.

## Main branch contract
- main is always deployable and represents the current baseline.
- Changes merged to main must not break the smoke checks in scripts/smoke_check.py.
- Experimental work lives in feature branches or experiments/ and is not part of the baseline API.

## Versioning
- Versions follow MAJOR.MINOR.PATCH.
- The baseline version is recorded in VERSION and tool.poetry.version in pyproject.toml.
- Docker images must be built with the matching version label.

## Tagging a release
1. Update VERSION and pyproject.toml to the target version.
2. Update CHANGELOG.md with the release notes.
3. Build the Docker image with CYGNET_VERSION set to the release version.
4. Tag the commit:
   git tag -a vX.Y.Z -m "Baseline vX.Y.Z"
5. Push the tag:
   git push origin vX.Y.Z

Notes:
- Never reuse an existing tag. If v1.0.0 already exists, release changes as v1.0.1 or later.
