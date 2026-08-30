# Triple H Manager — Project History and V2 Context

## 1. Purpose

Triple H Manager is a Python desktop application that manages several Haraj accounts. Its intended capabilities are:

- Store multiple accounts securely.
- Update all existing ads for each account.
- Publish new service ads for selected or all accounts.
- Read ad content from a public Google Sheet.
- Use a different title and body for each account.
- Keep each account isolated in its own Chrome profile.
- Continue processing when one account or advertisement fails.
- Show logs and operational status in the desktop UI.

The initial business use case is advertising water-tanker delivery services in Saudi cities, starting with Hail.

## 2. Current technology

- Python 3.10 or newer.
- Tkinter/ttk desktop interface.
- Selenium 4 with Google Chrome.
- Selenium Manager for compatible ChromeDriver resolution.
- `cryptography.fernet` for encrypted account storage.
- Public Google Sheets data read through a CSV/export URL.
- macOS is the primary development environment, with Windows support intended.

Repository:

```text
https://github.com/0x5441/triple-h-manager
```

The latest working project was located under the repository's `manager` directory.

## 3. Legacy project shape

Important legacy files include:

```text
manager/
├── app.py
├── bot.py
├── storage.py
├── google_sheets.py
├── create_profile.py
├── test_profile.py
├── getcookies.py
├── testcookies.py
├── requirements.txt
├── run_mac.command
└── run_windows.bat
```

The legacy version grew incrementally. UI logic, worker orchestration, status handling, Selenium automation, and persistence became too tightly coupled. This is the main reason for rebuilding V2 instead of continuing to patch the same files.

## 4. Account management

The application stores accounts containing at least:

```python
{
    "name": "account display name",
    "username": "Haraj mobile/account number",
    "password": "encrypted at rest",
    "ads": []
}
```

Planned V2 fields:

```python
{
    "id": "stable account id",
    "name": "display name",
    "username": "Haraj account number",
    "password": "encrypted at rest",
    "paused": False,
    "last_status": "لم يعمل بعد",
    "last_run_at": "",
    "ads": []
}
```

Required account features:

- Add, edit, and delete an account.
- Hide passwords in the UI.
- Encrypt stored account records.
- Pause and reactivate an account without deleting it.
- Skip paused accounts during run-all operations.
- Display last status and last run time.
- Preserve profiles when an account record is deleted unless deletion is explicitly requested.

## 5. Session management decision

Cookies-only testing was attempted and rejected because a Haraj login session may depend on additional browser storage and state.

The selected approach is one independent Chrome profile per account:

```text
manager/data/profiles/{username}/
```

The standalone profile tests `create_profile.py` and `test_profile.py` worked successfully on macOS.

Expected profile behavior:

1. Open Chrome with the account's `--user-data-dir`.
2. Visit Haraj.
3. If `[data-testid="user-menu"]` is present, reuse the saved session.
4. If the session is absent or expired, perform the normal login using the stored credentials.
5. Allow the user to complete additional verification manually when required.
6. Never open the same profile in two Chrome processes simultaneously.

Planned profile features:

- Create a profile automatically on first use.
- Validate an existing session.
- Refresh an expired profile session.
- Show clear errors when the profile is already in use.
- Keep the browser operation inside a service rather than the UI.

## 6. Haraj login flow

Known selectors:

```text
Login link:             [data-testid="login-link"]
Username input:         [data-testid="auth_username"]
Continue username:      [data-testid="auth_submit_username"]
Password input:         [data-testid="auth_password"]
Submit login:           [data-testid="auth_submit_login"]
Logged-in user menu:    [data-testid="user-menu"]
```

Login must not be executed unconditionally. The application should check the saved profile session first.

## 7. Existing-ad update flow

Each account may have several saved Haraj advertisement URLs.

For each account:

1. Open the account's Chrome profile.
2. Ensure the account is logged in.
3. Visit each stored ad URL.
4. Wait for the update button.
5. Click the update button.
6. Record success or failure.
7. Continue to the next ad after a failure.
8. Close Chrome in `finally` before moving to the next account.

Known selector:

```text
[data-testid="update-button"]
```

## 8. New-ad publishing flow

The known flow for publishing a Haraj service advertisement is:

1. Open `https://haraj.com.sa/`.
2. Click Add Offer.
3. Select Add Service.
4. Tick the agreement checkbox.
5. Continue through step two.
6. Continue through step four.
7. Fill the title.
8. Replace the mobile field value completely.
9. Fill the body.
10. Submit the advertisement.

Known selectors in order:

```text
Add offer:              [data-testid="add-post-button"]
Add service:            [data-testid="post-type-458-label"]
Agreement:              [data-testid="step-two-agreement-checkbox"]
Continue step two:      [data-testid="step-two-resume"]
Continue step four:     [data-testid="step-four-resume"]
Title:                  [data-testid="new-post-title"]
Mobile:                 [data-testid="step-five-mobile-input"]
Body:                   [data-testid="add-post-bodyText"]
Submit:                 [data-testid="post-submit"]
```

The required field order is:

```text
title -> mobile -> body -> submit
```

Before entering the mobile number, the program must remove the existing value completely. It should select all content, delete it, clear it, dispatch input/change events if necessary, enter the new value, and verify the final value before proceeding. If verification fails after one retry, the program must stop that ad and must not submit it.

The contact number used during the project was discussed in two inconsistent forms:

```text
966592099662
96659209962
```

Do not guess which is correct. V2 must read the phone from configuration or the Google Sheet and validate it. Ask the user to resolve inconsistent values before hardcoding any number.

Image upload has not been completed because the input selector and final expected behavior were not supplied. Do not invent the image workflow.

## 9. Google Sheets integration

The source spreadsheet is named `hararj` and was shared publicly. The application reads a selected tab from the public spreadsheet.

The UI requirement is:

- Enter or store the public Google Sheets link.
- Fetch the available tab names.
- Allow the user to select the advertisement tab from a dropdown.

A tab named `إعلانات وايت حائل` was created with five account-specific advertisements.

Columns used by the legacy application:

```text
account | title | body | phone | image | status
```

The required columns should be only:

```text
account | title | body
```

Optional columns:

```text
phone | image | status
```

Expected behavior:

- Match a row to an account by account name or username.
- Do not reuse rows already marked complete.
- Use a configured default phone only when the row phone is blank.
- Treat `image` as optional until image upload is implemented.
- Support dry-run publishing that fills the form but does not click Submit.
- Public read access does not automatically authorize API writes. If the application cannot update the Sheet, store processed row keys locally and state that limitation clearly.

## 10. UI requirements

The current UI includes:

- Account table.
- Account add/edit/delete controls.
- Advertisement link list.
- Update selected/all buttons.
- Publish selected/all buttons.
- Headless option.
- Dry-run option.
- Google Sheets settings.
- Operation log and completion summary.

V2 additions:

- Pause/reactivate selected account.
- Refresh selected account profile session.
- Display account status.
- Display last run time.
- Show whether a profile/session is valid, expired, busy, or failed.
- Disable conflicting controls while a job is running.
- Keep all Tkinter mutations on the main UI thread by processing queued events.

## 11. Status model

Use a centralized enum or constants rather than scattered free-form text.

Minimum states:

```text
IDLE             جاهز
NEVER_RUN        لم يعمل بعد
RUNNING          قيد التشغيل
SUCCESS          نجح
FAILED           فشل
PAUSED           متوقف مؤقتًا
SESSION_VALID    الجلسة صالحة
SESSION_REFRESHED تم تجديد الجلسة
PROFILE_BUSY     البروفايل مستخدم حاليًا
```

Store timestamps using local time in a consistent format, for example:

```python
datetime.now().strftime("%Y-%m-%d %H:%M")
```

## 12. Error handling and logging

- A failed account must not stop remaining accounts.
- A failed advertisement must not stop remaining advertisements.
- Save screenshots under `data/errors` when Selenium fails.
- Use concise user-facing messages and detailed logs for diagnosis.
- Close the driver in `finally`.
- Distinguish login failure, session expiration, missing element, profile busy, Sheet read failure, and submit failure.
- Never mark an advertisement successful merely because Selenium clicked the button. Verify a meaningful post-submit condition.

## 13. macOS issues already encountered

### Gatekeeper warning

macOS initially blocked ChromeDriver because it was not yet approved. The safe resolution was approving the specific ChromeDriver under Privacy & Security rather than disabling Gatekeeper globally.

### Chrome/ChromeDriver mismatch

An old Homebrew ChromeDriver on PATH caused `SessionNotCreatedException` because its major version did not match Chrome. The discovered path was:

```text
/opt/homebrew/bin/chromedriver
```

The old executable was moved aside so Selenium Manager could resolve a compatible driver. Do not hardcode an obsolete ChromeDriver binary into V2.

## 14. Security and repository hygiene

Never commit:

```text
data/
profiles/
*.enc
*.key
.env
cookies.json
credentials.json
*_error.png
*_failed.png
__pycache__/
.venv/
```

Chrome profiles contain authenticated sessions and must be treated as credentials.

The repository previously contained test failure screenshots. Generated screenshots should not remain under source control.

## 15. Recommended V2 architecture

```text
triple-h-manager/
├── main.py
├── AGENTS.md
├── requirements.txt
├── app/
│   ├── config.py
│   ├── models/
│   │   ├── account.py
│   │   ├── ad.py
│   │   └── result.py
│   ├── services/
│   │   ├── account_service.py
│   │   ├── profile_service.py
│   │   ├── publish_service.py
│   │   ├── update_service.py
│   │   └── job_runner.py
│   ├── browser/
│   │   ├── browser_factory.py
│   │   ├── haraj_page.py
│   │   └── selectors.py
│   ├── storage/
│   │   ├── account_store.py
│   │   ├── settings_store.py
│   │   └── google_sheets.py
│   └── ui/
│       ├── main_window.py
│       ├── accounts_tab.py
│       ├── publishing_tab.py
│       └── logs_tab.py
├── docs/
│   └── PROJECT_HISTORY.md
├── legacy/
└── tests/
```

Do not create layers only for appearance. Keep interfaces small and dependencies one-directional.

## 16. Recommended rebuild order

1. Preserve the current working version as legacy.
2. Create a `v2-rebuild` branch.
3. Add models, configuration, and encrypted storage.
4. Add BrowserFactory and profile management.
5. Add Haraj login/session validation.
6. Add existing-ad update workflow.
7. Add Google Sheets reader.
8. Add dry-run new-ad publishing.
9. Add verified live publishing.
10. Add pause/reactivate, profile refresh, and last status.
11. Build the final UI over the services.
12. Add migration and acceptance tests.

## 17. Definition of done for V2

V2 is not complete merely because the interface opens.

It is complete when:

- Existing encrypted account data can be migrated safely.
- Every account uses an isolated persistent profile.
- Saved valid sessions bypass login.
- Expired sessions can be renewed.
- Paused accounts are skipped.
- Last status and time persist and appear in the UI.
- Update-all continues after failures.
- Publish-all reads the selected Sheet tab and matches accounts correctly.
- Dry-run never submits.
- Live submit is verified by a meaningful success condition.
- The UI remains responsive during jobs.
- Tests cover storage, profiles, Sheet parsing, job orchestration, and failure continuation.
- No secrets or profiles are tracked by Git.

## 18. First task for Codex

After reading this file and `AGENTS.md`, Codex should inspect the live repository and report:

1. What it understands about the project.
2. The current file/dependency map.
3. Conflicts between this history and the current code.
4. Risks in preserving or migrating existing account data.
5. A staged V2 implementation plan.

Codex must not begin the rebuild until the user approves that plan.

