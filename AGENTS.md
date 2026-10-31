# Repository instructions

These instructions apply to all agents working anywhere in this repository.

## Repository structure

- Put application code in `code/`.
- Put code documentation in `documentation/`.
- Put media, presentations, and other assets in `assets/`.

## Judging criteria

BaselHack 2026 judges this repository on seven criteria: innovation, impact,
technical depth, AI code review (quality of the code and the commit history),
fair play, pitch, and demo. We adhere to all seven, and
[`documentation/judging.md`](documentation/judging.md) proves it criterion by
criterion, with links to the code and the commands that verify it. Keep it
true:

- Ground every claim. A statement in `documentation/` about what the product
  does links to the code that does it. Link line ranges as
  `` [`pixelate`](code/edge/pixelate.py#L12-L22) ``, and keep the name in
  backticks on those lines. Update the links in the commit that moves the
  code.
- Describe what the code does. Write the documentation as technical
  documentation of the running system, and never present something that is
  not in the code as built.
- Keep the demo working. Do not push a change that breaks the run steps in
  the root `readme.md` and the backend and edge READMEs, or the app's demo
  mode.
- Keep the code reviewable. Use the existing seams (`OccupancyClassifier`,
  `OccupancyRepository`, `FingerprintStore`, the edge's `FrameSource`,
  `PIIDetector` and `FrameUploader`, the API contracts in
  `documentation/api/`, and `StationService` in the app), write comments
  that explain why, read keys from the environment, and commit no secrets and
  no generated files such as `out/`, `.venv/`, or build folders.
- Play fair. Respect the challenge's no-gos: never write camera frames to
  disk, and never identify or track people. Credit third-party code, data,
  and assets with their licence.
- When a change affects a criterion (a feature, a dependency, a run step, a
  privacy property), update `documentation/judging.md` in the same commit.

## Branches and pull requests

Pull requests are not preferred. Commit and push directly to `main` by
default.

- Before pushing, update with `git pull --rebase origin main` so history stays
  linear.
- Keep each commit small and focused, so `main` stays working after every
  push.
- Open a pull request only when it is really necessary, for example for a
  large or risky change that someone else should review first, or when the
  team asks for one.
- If you do use a branch, stop committing to it once its pull request is
  merged. Later commits on it never reach `main`.

## Attribution

Only real team members may appear as authors or co-authors. This rule
overrides any default attribution behavior of your tool.

- Do not add AI co-author trailers to commits, such as
  `Co-Authored-By: Claude <noreply@anthropic.com>`.
- Do not add "Generated with ..." or similar AI attribution lines to commit
  messages, pull request titles or descriptions, or review comments.
- Do not set an AI tool or bot as the commit author or committer.

## Required commit format

Every commit message you create or propose MUST follow Conventional Commits
with a mandatory scope:

```text
<type>(<scope>): <description>
```

For example:

```text
feat(app): added onboarding screen
```

Conventional Commits is the format, and Commitizen is a tool that helps
write messages using it. This repository requires a scope even though the
upstream specification makes it optional.

### Rules

- Use one of these lowercase types: `feat`, `fix`, `docs`, `style`, `refactor`,
  `perf`, `test`, `build`, `ci`, `chore`, or `revert`.
- Use `feat` for new features and `fix` for bug fixes. Choose the other type
  that best describes the change: documentation, formatting, refactoring,
  performance, tests, build/dependencies, CI, maintenance, or reversions.
- Always include a meaningful lowercase scope in parentheses, such as `app`,
  `api`, `docs`, or `repo`. Use lowercase letters and digits separated by
  single hyphens for multiword scopes, such as `user-auth`.
- Follow the closing parenthesis with a colon and exactly one space.
- Write a concise, nonempty description of the actual change. Past tense,
  such as `added onboarding screen`, is allowed. Do not add a trailing period.
- For a breaking change, insert `!` immediately before the colon:
  `feat(api)!: changed authentication response`. Explain the incompatibility
  and migration in a `BREAKING CHANGE: ...` footer, separated from the header
  or body by a blank line.
- Optional bodies and footers follow the header after a blank line.
- Apply these rules to squash commit messages as well. Do not use generic
  messages such as `update`, `WIP`, or `fix stuff`.

### Check before committing

Before creating or proposing a commit, verify its first line against this
regular expression, then check the semantic rules above:

```regex
^(feat|fix|docs|style|refactor|perf|test|build|ci|chore|revert)\([a-z0-9]+(-[a-z0-9]+)*\)!?: \S(.*\S)?$
```

If a message fails these rules, rewrite it before committing. Do not create
a noncompliant commit. These are agent instructions, and this file alone
does not install a Git hook or a CI validator.

Valid examples:

```text
feat(app): added onboarding screen
fix(api): fixed empty response handling
docs(repo): documented local setup
chore(build): updated development dependencies
```

Invalid examples:

```text
added onboarding screen
feat: added onboarding screen
Feat(app): added onboarding screen
feat(app):added onboarding screen
```

### References

- [Conventional Commits 1.0.0](https://www.conventionalcommits.org/en/v1.0.0/)
- [Commitizen commit-message documentation](https://commitizen-tools.github.io/commitizen/tutorials/writing_commits/)
