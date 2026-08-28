# Release Checklist

This document is for an app maintainer. It gives the steps to release a new version of the app.

!!! important
    Before starting, make sure your **local** `develop`, `main`, and (if applicable) the current LTM branch are all up to date with upstream!

    ```
    git fetch
    git switch develop && git pull # and repeat for main/ltm
    ```

Select the route for your release:

- For an LTM release, go [here](#ltm-releases).
- For a patch release from `develop`, go [here](#all-releases-from-develop).
- For a minor release, do [Minor Version Bumps](#minor-version-bumps), then [All Releases from `develop`](#all-releases-from-develop).

## Minor Version Bumps

### Update Requirements

Each minor version release must refresh `poetry.lock`, so that the file lists the most recent stable release of each package. To do this:

0. Run `poetry update --dry-run`. Poetry then names each available package update and the version it would install. This needs an environment that you made from the lock file, with `poetry install`.
1. Read the release notes of each requirement. Look for a breaking change or another important change.
2. Run `poetry update <package>` to change the package versions in `poetry.lock`.
3. A version constraint in `pyproject.toml` can block a new release. For example, `Django ~3.1.7` never installs `Django >=4.0.0`. Change such a constraint by hand in `pyproject.toml`.
4. Run `poetry install` to install the new versions.
5. Run each test with `poetry run invoke tests`. Check that the UI and the API work correctly.

### Update Documentation

Update the compatibility matrix if it changes, for example when the minimum supported Nautobot version moves.

Commit each documentation change from the sections below before you continue with the release.

!!! tip
    Fire up the documentation server in your development environment with `poetry run mkdocs serve`! This allows you to view the documentation site locally (the link is in the output of the command) and automatically rebuilds it as you make changes.

### Verify the Installation and Upgrade Steps

Obey the [installation instructions](../admin/install.md) and make a new production installation of the app. If you can, also do a test of the [upgrade process](../admin/upgrade.md) from the last release.

This step does the whole install process *as the documentation gives it*. It finds an error or an omission in that documentation, and it keeps the documentation current with each release.

---

## All Releases from `develop`

### Verify CI Build Status

Make sure that the continuous integration tests on the `develop` branch finish correctly.

### Run the Prepare Release Github Workflow

Run the [Prepare Release](https://github.com/jtdub/nautobot-app-ai-models/actions/workflows/prepare_release.yml) GitHub workflow.

1. Keep "Use workflow from" at the default `develop` branch.
2. Select the version bump type: prerelease, patch, minor, or major.
3. Enter the branch to release from. The default is `main`.
4. Enter the date of the release as YYYY-MM-DD, if you prepare the release early. The default is today.
5. Select **Run workflow**.

The workflow creates a release branch, changes the version, and generates the release notes. A release from `main` starts from `develop`. The workflow also opens a pull request to merge the release branch into the target branch. The generated release notes become the description of that PR.

### Review and Merge the Release PR

Read the release PR that the workflow created. Correct the release notes if you must. Merge the PR after CI finishes and a reviewer approves it.

A new major or minor version creates a new `docs/admin/release_notes/version_{major}.{minor}.md` file. Write the `Release Overview` section of that file by hand. Give a clear summary of the most important changes.

### Publish the Release

The Prepare Release workflow creates a draft release in GitHub. Check the release notes, the tag, and the target branch. Then publish the release.

### Sync the Release Back to `develop`

After you publish a release from `main`, a new PR appears. It merges the changes from `main` back into `develop` and moves the version to the next development version, for example `1.4.3a1`. Read the PR and merge it after CI finishes and a reviewer approves it.

### Sync the Release to `next`

A release from `main` also creates a PR that forward-ports the changes from `main` into `next`. The `next` branch then stays current.

Without a `next` branch, this step does not run.

## Legacy Documentation for Releases

Use the process above for each release. The steps below are the old manual process, kept for reference.

### Bump the Version

Change the package version with `poetry version` ([poetry docs](https://python-poetry.org/docs/cli/#version)). The command shows the current version. With a valid bump rule, it changes the version and writes the result to `pyproject.toml`.

The new version must be a valid semver string or a valid bump rule: `patch`, `minor`, `major`, `prepatch`, `preminor`, `premajor`, or `prerelease`. Use a bump rule where you can.

!!! warning
    This guide uses `1.4.2` as the new version in its examples, so change it to match the version you bumped to in the previous step! Every. single. time. you. copy/paste commands!

Show the current version with no arguments:

```no-highlight
> poetry version
nautobot-ai-models 1.0.0-beta.2
```

Move a pre-release version with `prerelease`:

```no-highlight
> poetry version prerelease
Bumping version from 1.0.0-beta.2 to 1.0.0-beta.3
```

For a major version, use `major`:

```no-highlight
> poetry version major
Bumping version from 1.0.0-beta.2 to 1.0.0
```

For a minor version, use `minor`:

```no-highlight
> poetry version minor
Bumping version from 1.0.0 to 1.1.0
```

For a patch version, use `patch`:

```no-highlight
> poetry version patch
Bumping version from 1.1.0 to 1.1.1
```

### Update the Changelog

!!! note
    - This project uses `towncrier` to track human readable changes, so all merged PRs will have one or more entries in the release notes.
    - The changelog must adhere to the [Keep a Changelog](https://keepachangelog.com/) style guide for any manual changes you may need to make.
    - You will need to have the project's poetry environment built at this stage, as the towncrier command runs **locally only**. If you don't have it, run `poetry install` first.
    - You can also set the version explicitly with `invoke generate-release-notes --version 1.4.2` if it needs to be different from what's in `pyproject.toml`.

First, create a release branch from `develop` with `git switch -c release-1.4.2 develop`. Then generate the release notes with `invoke generate-release-notes`.

A new major or minor version creates a new `docs/admin/release_notes/version_{major}.{minor}.md` file. Write the `Release Overview` section of that file by hand. Give a clear summary of the most important changes.

Stage the remaining files, for example with `git add mkdocs.yml pyproject.toml`. Check each change with `git diff --cached`. A release of `1.4.2` updates the release notes in `docs/admin/release_notes/version_1.4.md`, stages that file, and removes each fragment that is now in the release notes.

Commit the staged changes with `git commit -m "Release v1.4.2"`, then run `git push`.

### Submit Release Pull Request

Open a pull request named `Release v1.4.2` to merge your release branch into `main`. Copy the release notes into the body of the pull request.

!!! important
    Do not squash merge this branch into `main`. Make sure to select `Create a merge commit` when merging in GitHub.

Merge the PR after CI finishes.

### Create a New Release in GitHub

Draft a [new release](https://github.com/jtdub/nautobot-app-ai-models/releases/new) with these values.

* **Tag:** Input current version (e.g. `v1.4.2`) and select `Create new tag: v1.4.2 on publish`
* **Target:** `main`
* **Title:** Version and date (e.g. `v1.4.2 - 2024-04-02`)

Select "Generate Release Notes". Then edit the generated content:

- Cut each generated entry down to the username of the contributor. For example, change `* Updated dockerfile by @nautobot_user in https://github.com/jtdub/nautobot-app-ai-models/pull/123` to `* @nautobot_user`.
    - This should give you the list for the new `Contributors` section.
    - Make sure there are no duplicated entries.
- Replace the `What's Changed` section with the change description from the release PR, which towncrier generated.
- Leave the `New Contributors` list as it is, if the list exists.

The release notes then look like this:

```markdown
## What's Changed

**Towncrier generated Changed/Fixed/Housekeeping etc. sections here**

## Contributors

* @alice
* @bob

## New Contributors

* @bob

**Full Changelog**: https://github.com/jtdub/nautobot-app-ai-models/compare/v1.4.1...v1.4.2
```

Publish the release.

### Create a PR from `main` back to `develop`

First, sync your `main` branch with the upstream changes: `git switch main && git pull`.

Create a branch from `main` named `release-1.4.2-to-develop`. Run `poetry version prerelease` to move the development version to the next release.

For example, after a release of `v1.4.2`:

```no-highlight
> git switch -c release-1.4.2-to-develop main
Switched to a new branch 'release-1.4.2-to-develop'

> poetry version prerelease
Bumping version from 1.4.2 to 1.4.3a0

> git add pyproject.toml && git commit -m "Bump version"

> git push
```

!!! important
    Do not squash merge this branch into `develop`. Make sure to select `Create a merge commit` when merging in GitHub.

Open a PR from `release-1.4.2-to-develop` against `develop`. Wait for CI to pass, then merge it.

### Final checks

CI now runs, or has finished, for the `v1.4.2` tag. It publishes a package to PyPI and adds it to the GitHub Release. Check that this happened.

ReadTheDocs also builds the documentation for the tag. If you read this page online, refresh it and look for the new version in the fly-out menu at the bottom right.

The release is complete.

## LTM Releases

A project with a Nautobot LTM compatible release does each development and release step on the `ltm-x.y` branch. The `x.y` is the LTM version of Nautobot that the branch works with, for example `2.4`.

The process is almost the same as a [release from `develop`](#all-releases-from-develop). You release directly from the LTM branch, so no branch sync is necessary afterward.

After you publish the release, open a separate PR against `develop`. It copies each LTM release note into the latest documentation, so that a reader can find it.

### Legacy Documentation for LTM Releases

Use the automated process for each LTM release. The steps below are the old manual process, kept for reference.

1. Make sure that CI passes on your `ltm-2.4` branch.
2. Create a release branch from the `ltm-2.4` branch: `git switch -c release-2.4.99 ltm-2.4`.
3. Move the patch version with `poetry version patch`. For a backported feature rather than a bug fix, move the minor version with `poetry version minor`.
4. Generate the release notes: `invoke generate-release-notes --version 2.4.99`.
5. Move the release notes from `docs/admin/release_notes/version_X.Y.md` to `docs/admin/release_notes/version_2.4.md`.
6. Add each change, run `git commit -m "Release v2.4.99"`, then run `git push`.
7. Open a PR against `ltm-2.4`. After CI passes, select `Create a merge commit`. Do not squash.
8. Create a new release in GitHub. Use the steps [here](#create-a-new-release-in-github), with one difference: for an LTM release, **clear the "Set as the latest release" checkbox**.
9. Open a separate PR against `develop`. It copies each LTM release note into the latest documentation.

These commands copy the release notes from the `ltm-2.4` branch to the `develop` branch:

```no-highlight
> git switch develop

> git pull

> git switch -c release-2.4.99-notes-to-develop develop

> git checkout ltm-2.4 docs/admin/release_notes/version_2.4.md

> git add docs/admin/release_notes/version_2.4.md && git commit -m "Update release notes from LTM 2.4 to develop"

> git push
```

Open a PR from `release-2.4.99-notes-to-develop` against `develop`. Wait for CI to pass, then merge it.
