# Contributing

Thanks for helping improve Island Finder.

## Development setup

Use Node.js 22.12 or newer, Python 3.11/3.12, and `uv`:

```sh
npm run setup
npm run check
```

The same commands are supported in macOS Terminal and Windows PowerShell.

## Safety rules

- Keep the automation stopped or in dry-run mode while changing recognition,
  retries, controller transport, or state transitions.
- Never send controller input from a test. Hardware tests must be explicitly
  invoked and must release every pressed button.
- A candidate island must enter `awaitingDecision`; do not automatically
  confirm the user's final keep/reject choice.
- Unknown, loading, low-confidence, and no-signal frames must not trigger blind
  input.
- Page-transition retries must stay bounded and page-confirmed.

## Pull requests

- Add regression coverage for behavior changes.
- Run `npm run check` before submitting.
- Do not commit `data/`, firmware backups, full-frame account captures, device
  serial numbers, absolute home-directory paths, credentials, or API tokens.
- If a visual fixture is necessary, crop it to the minimum region and remove
  names, avatars, IDs, timestamps, and unrelated account or library content.
- Explain hardware and operating-system validation separately from simulated or
  unit-test evidence.

By contributing, you agree that your contribution is licensed under the MIT
License.
