# Contributing to the App

The project has a light [development environment](dev_environment.md) that uses `docker-compose`. Use it for local development and to run the tests.

The project obeys the Network to Code software development guidelines. It uses these tools:

- Python linting and formatting: `pylint` and `ruff`.
- YAML linting is done with `yamllint`.
- Django unit tests, to make sure that the app works correctly.
- Django Template linting: `djlint`
- Django Template formatting: `djhtml`

[mkdocs](https://www.mkdocs.org/) builds the documentation. The [Docker development environment](dev_environment.md#docker-development-environment) starts a container that hosts a live documentation site on [http://localhost:8001](http://localhost:8001). The site refreshes when you change a local file.

## Creating Changelog Fragments

Each pull request to `next` or to `develop` must include a changelog fragment file in the `./changes` directory.

Name the file after your GitHub issue number and the fragment type, for example `2362.added`. The valid types are `added`, `changed`, `deprecated`, `fixed`, `removed`, and `security`.

Write the change summary in the file as plain text. Use a complete sentence. Start it with a capital letter, end it with a full stop, and write it in the past tense. Each line makes one entry in the release notes. Use more lines in the same file for more entries in the same category. Use more files for entries in different categories.

!!! example

    **Wrong**
    ```plaintext title="changes/1234.fixed"
    fix critical bug in documentation
    ```

    **Right**
    ```plaintext title="changes/1234.fixed"
    Fixed critical bug in documentation.
    ```

!!! example "Multiple Entry Example"

    This will generate 2 entries in the `fixed` category and one entry in the `changed` category.

    ```plaintext title="changes/1234.fixed"
    Fixed critical bug in documentation.
    Fixed release notes generation.
    ```

    ```plaintext title="changes/1234.changed"
    Changed release notes generation.
    ```

## Branching Policy

The branching policy includes the following tenets:

- The `develop` branch holds the next planned major and minor version.
- Start a PR that adds a feature from the `develop` branch.
- Start a PR that fixes an issue in the Nautobot LTM compatible release from the latest `ltm-<major.minor>` branch, not from `develop`.

AI Models obeys semantic versioning from 1.0. Minor versions can follow each other quickly, to keep pace with the feature set.

## Testing Standards

Each contribution must include test coverage. Tests keep the app stable, stop a regression, and give confidence in a release.

The standards are:

- A new feature **must** include unit tests.
- A bug fix **must** include a test that shows the reported issue and stops a regression.
- Write a test with the Nautobot base test cases, and obey the patterns of the project.
- A pull request **must not** break an existing test.
- A pull request that lowers the test coverage can be asked for more tests before approval.
- The tests must pass locally and in CI before a merge.

### Backporting to Older Releases

To backport a fix to an earlier major or minor version, open an issue, comment on an existing issue, or write in the [Network to Code Slack](https://networktocode.slack.com/), in the `#nautobot` channel.

A maintainer then creates a `release-X.Y` branch for your PR, and makes a new release after the merge.

## Release Policy

AI Models has no release schedule. New features go into a minor version.

The [release checklist](./release_checklist.md) gives the steps that a maintainer obeys to make a release.
