# SP Telegram

SP Telegram is a PySide6 desktop operations application for authorized Telegram account, group, member, campaign, scheduling, monitoring and local-data workflows. The desktop keeps the existing SQLite database (`data/tg_control.db`) and Telegram session layout for upgrade compatibility.

## Desktop source setup (Windows)

Use the project-local virtual environment:

```powershell
cd "C:\path\to\sp-telegram"
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe main.py
```

For QA tools:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m pytest -q
.\scripts\run_phase83_windows_qa.ps1
```

The automated desktop QA uses disposable databases, runtime folders and Qt settings. It does not connect Telegram accounts or modify the normal `data/`, `backups/`, `exports/` or `logs/` directories.

Production source does not select mock Telegram or mock license adapters at runtime. Automated mocks remain under `tests/` only.

## First run

1. Start the application with `.\.venv\Scripts\python.exe main.py`. The required local folders and SQLite schema are created automatically.
2. Open **Settings > Telegram**. Enter the API ID and API hash issued to your own Telegram application at [my.telegram.org](https://my.telegram.org), then choose **Test API Settings** and **Save Settings**. Never share the API hash.
3. Open **Accounts** and choose **Add Account**. Complete Telegram's authorization prompts only for an account you own or are authorized to operate. The resulting local session grants account access and must be protected like a password.
4. Add or discover groups only where that account has the required authorization. Verify account and group permissions before enabling collection, posting, scheduling or member workflows.
5. If your deployment uses paid features, configure the public license client values described below and activate a key on the **Licensing** page. Core startup and local data protection do not require the license server to be online.

Runtime data stays under the project root:

| Path | Purpose |
| --- | --- |
| `data/tg_control.db` | Local SQLite application database |
| `data/sessions/` | Sensitive Telegram authorization sessions |
| `data/cache/` and `data/media/` | Re-creatable cache and adopted campaign media |
| `backups/` | Local database backups |
| `exports/` | Operator-requested exports |
| `logs/app.log` | Redacted application diagnostics |

Back up the database and sessions securely before moving or upgrading an installation. Do not commit, email or share session files, databases, license keys or environment files.

## Troubleshooting desktop startup

- **Database cannot be opened:** close other copies of SP Telegram and confirm `data/` is writable. Do not delete `tg_control.db`, `-wal` or `-shm` files to work around a lock; preserve them and make a backup first.
- **Telegram API settings fail:** confirm the API ID is numeric, re-enter the API hash, verify network access to Telegram and use credentials from your own `my.telegram.org` application.
- **An account is unauthorized or disconnected:** reconnect from **Accounts**. Do not copy an unknown session file into `data/sessions/`.
- **License activation fails:** verify `LICENSE_API_BASE_URL` is HTTPS in production, `SP_LICENSE_PUBLIC_KEY_B64` matches the server signing key and the license service is reachable. Local HTTP is allowed only for an explicitly enabled loopback development server.
- **The window fails during launch:** run `.\scripts\run_phase83_windows_qa.ps1`, then inspect `logs/app.log`. This QA runner is isolated from operator data.

## License service

The separate `license_server/` project is the production licensing boundary. It uses FastAPI, PostgreSQL/SQLAlchemy, Alembic and Ed25519 signed entitlements. The server retains the private signing key; the desktop receives only the public verification key.

Generate a signing keypair locally:

```powershell
python .\license_server\scripts\generate_signing_keys.py
```

The command prints a server-only private value and a desktop public value. Never commit the private value.

Configure the server from `license_server/.env.example`, then install its dependencies in a separate environment and apply migrations:

```powershell
python -m venv license_server\.venv
.\license_server\.venv\Scripts\python.exe -m pip install -r license_server\requirements.txt
# load your secure server environment values
.\license_server\.venv\Scripts\alembic.exe -c license_server\alembic.ini upgrade head
.\license_server\.venv\Scripts\python.exe -m license_server.app.cli seed-plans
.\license_server\.venv\Scripts\python.exe -m uvicorn license_server.app.main:app --host 127.0.0.1 --port 8001
```

For local desktop-to-server development only, run the one-time configurator after `license_server/.env` is ready:

```powershell
# Derives only the matching PUBLIC key from license_server/.env and writes desktop-license.env.
.\.venv\Scripts\python.exe scripts\configure_desktop_license.py

# Future launches no longer need temporary set/$env commands.
.\.venv\Scripts\python.exe main.py
```

Production releases must use an HTTPS `LICENSE_API_BASE_URL` and the matching Ed25519 public key. Server private keys, admin tokens, database passwords and payment credentials never belong in the desktop repository or executable.

## License plans

The service seeds the exact plans used by the desktop: Starter at $8/month (1 device), Pro at $10/month (1 device), and Ultimate at $12/month (2 devices). Plan features, limits, status, expiry and device activation are server-controlled and signed. The desktop cannot locally promote itself to another plan.

## Data and security

Normal database backup/restore remains available according to the existing safety policy. Telegram session files are not included in ordinary backups by default. License expiry, suspension or downgrade never deletes accounts, groups, members, campaign history, schedules, logs, backups or settings.

Telegram FloodWait, account restrictions, privacy controls and group permissions are always respected. SP Telegram does not automatically rotate to another account to evade a restriction.

## Runtime directories

Runtime state is intentionally excluded from source release archives:

```text
data/tg_control.db*
data/sessions/*.session*
logs/*.log
.venv/
license_server/.env
private signing keys
```

Automated tests are retained in `tests/`, but are not part of normal application runtime behavior.

## Release boundary

This source tree is prepared for the later Windows packaging phase. PyInstaller, installer generation and portable release packaging are intentionally not performed here.
