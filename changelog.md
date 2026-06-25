## 2026.6.25

### New Features

#### Chat Navigation — Auto Browser Switch
- Added **Auto-switch chat** option in Settings: when enabled, pressing `Ctrl+Shift+[` or `Ctrl+Shift+]` will navigate the browser to the selected conversation automatically, not just switch the reading focus.
- The browser navigates using the conversation's chat ID extracted from the Messenger URL (`/t/<chat_id>`).

#### UserScript Version Check
- The add-on now reads the required UserScript version directly from `universal.user.js` at runtime — no hardcoded version string in Python.
- On first push after NVDA starts, if the installed UserScript version does not match the required version, the add-on automatically opens the update URL in a new browser tab via the UserScript itself.
- The update page now shows a confirmation message ("Updated to version X") instead of raw source code.

#### Upgrade Detection in Install Wizard
- `onInstall` now detects whether this is a **fresh install** or an **upgrade** by checking for an existing add-on folder.
  - Fresh install: runs the full Tampermonkey setup wizard as before.
  - Upgrade: shows a dedicated dialog prompting the user to update the UserScript, with a **Copy Script URL** button.

### Settings Panel Redesign
- Reorganized the Messenger Access settings panel into three sections ordered by frequency of use:
  1. **Behavior** — checkboxes used regularly (beep, auto-jump, auto-switch chat).
  2. **UserScript** — version status display, Check for Update button, Copy Script URL button.
  3. **Advanced** — Install UserScript button (first-time setup only).

### Bug Fixes
- Fixed a navigation loop where `_pending_command` was not cleared after being served, causing the UserScript to re-execute the same navigate command after page reinitialisation.
- Fixed `isNavigating` guard never resetting on Messenger (a SPA), which permanently blocked polling after the first navigation. A 4-second fallback timeout now resets the flag.
- Switched from `location.href =` to `location.assign()` for chat navigation to better handle SPA behavior.
- Reduced poll interval from 5000 ms to 1500 ms for more responsive chat switching.
- `processChatMirror` and `pollCommand` are now both blocked while navigation is in progress to prevent stale data being pushed back to the add-on mid-navigation.

## 2026.6.5

- fix settings panel bug

## 2026.6.1

- initial release

## 2026.5.31

- beta release