# Contributing

This is a product repository; outside contributions are by invitation. The rules below apply to everyone working on it, people and AI agents alike.

## Branches and pull requests

- Work on a feature branch, open a pull request, merge only with green CI.
- One pull request, one purpose. Describe what changed, why, and how it was checked.

## Commit messages

- Imperative mood, English, at most 72 characters in the subject: `Add KRS ownership harvester`.
- Explain the reason in the body when it is not obvious.
- Commits written by an AI agent carry a `Co-Authored-By` trailer naming the agent. A human reviews and approves every merge.

## Tests

- Backend tests run offline; a guard blocks outgoing network calls.
- New behaviour comes with tests. Bug fixes come with a test that failed before the fix.

## Data

- Public sources with a lawful basis only. No personal data of private individuals in fixtures or logs.
- Secrets never enter the repository. See `SECURITY.md`.
