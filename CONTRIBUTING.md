# Contributing

## Changes

Create a short-lived branch for each change. Keep changes limited to one feature or defect.
Add a test that reproduces each defect before you correct it.

Before adding a guard, retry, or fallback, name the concrete failure that requires it.
Do not replace missing OCR data with invented text. Do not switch translation providers after an error.

Keep native OCR work outside the Decky process. Keep screenshot pixels outside the frontend RPC channel.
Keep user configuration, models, game files, and private screenshots out of Git.
Public illustrations require a privacy review and clear attribution.

## Checks

Run these commands before you submit a change:

```sh
pnpm typecheck
pnpm test
pnpm build
uv run ruff check .
uv run pytest -q
```

Keep diagnostic reports and device details outside the repository.
Do not add internal acceptance records to documentation.

## Upstream code

Record the upstream URL, commit, path, and license for each imported file.
Preserve copyright notices. Mark modified files in `THIRD_PARTY_NOTICES.md`.
Distribute the corresponding source archive with binary releases.

## Privacy

Use synthetic dialogue in tests and screenshots. Remove endpoint credentials and private game data from reports.
The project does not collect telemetry. A new network service requires an explicit user control.
