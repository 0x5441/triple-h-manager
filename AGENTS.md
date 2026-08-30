# AGENTS.md

## Project

This repository contains Triple H Manager, a Python desktop application for managing multiple Haraj accounts, updating existing ads, and publishing service ads from Google Sheets.

The current implementation is the legacy reference. New development should target a clean V2 architecture without breaking the legacy version until V2 is verified.

Before making changes, read `docs/PROJECT_HISTORY.md` and inspect the current source. If the documentation conflicts with live code, report the conflict before choosing a behavior.

## Engineering rules

- Keep the UI, business logic, browser automation, storage, and external data access in separate modules.
- Tkinter code must not contain Selenium page logic.
- Store every Haraj selector in one selectors module.
- Put Haraj navigation and element interaction behind a page-object class.
- Put account, profile, publishing, updating, and job orchestration logic in services.
- Use one independent Chrome profile per account under `data/profiles/{account_id}`.
- Never use the user's personal Chrome profile.
- Never run the same profile in two Chrome processes at the same time.
- Run accounts sequentially unless the architecture is deliberately changed and profile isolation is proven.
- A failure in one account or ad must not stop all remaining work.
- Use `WebDriverWait` for page state. Short delays may be used for stability, but do not rely on fixed sleeps alone.
- Do not add code intended to defeat CAPTCHAs, verification, rate limits, or site security controls.
- Keep passwords encrypted at rest.
- Never commit passwords, cookies, Chrome profiles, encryption keys, tokens, or account data.
- Preserve backward compatibility or provide an explicit migration for stored account data.
- Do not delete a profile automatically when an account is deleted.
- Do not perform destructive migrations without a backup and explicit approval.

## Required separation

Preferred V2 dependency flow:

```text
UI -> services -> Haraj page objects / storage / Google Sheets
```

The UI may submit jobs and consume queued events, but worker threads must not mutate Tkinter widgets directly.

## Verification

For every change:

1. Run Python syntax checks on changed Python files.
2. Run relevant automated tests.
3. Verify failure paths, not only success paths.
4. Review the diff for credentials and generated files.
5. Report changed files, tests run, and anything not tested against the live website.

Do not claim a Selenium workflow works on the live Haraj site unless it was actually tested there. Default live publishing tests to dry-run mode so the final submit button is not clicked unintentionally.

## Git expectations

- Build V2 in a dedicated branch such as `v2-rebuild`.
- Keep commits small and focused by feature.
- Do not rewrite or remove the working legacy version until V2 has passed acceptance testing.

