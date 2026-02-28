# Contributing

Thanks for contributing to SnowflakeCortexCLI.

## Discussion-first workflow

Before opening an Issue, start a GitHub Discussion to align on the problem and proposed approach.
When opening an Issue, include the Discussion URL.

## Safe collaboration defaults

Use these repository settings to keep `main` protected:

1. Require a pull request before merging.
2. Require at least 1 approval.
3. Require status checks to pass (at minimum: `Docs PR Check / docs-build`).
4. Dismiss stale approvals when new commits are pushed.
5. Restrict direct pushes to `main`.

These settings are managed in GitHub repository settings and cannot be fully enforced from repository files alone.

## What to check or change in the repo itself

These are the files in this repository that control contribution flow:

- `.github/ISSUE_TEMPLATE/config.yml`  
  Disables blank issues and sends contributors to Discussions first.
- `.github/ISSUE_TEMPLATE/problem-report.yml`  
  Requires a Discussion URL before an issue can be submitted.
- `.github/PULL_REQUEST_TEMPLATE.md`  
  Adds the pull request checklist contributors should follow.
- `.github/CODEOWNERS`  
  Defines default code owners used by required-review branch protection rules.

And these must be configured in GitHub UI (not in repo files):

- **Settings → Branches → Branch protection rules** for `main`.
- **Settings → General → Features** to ensure Discussions are enabled.
