# LabChem Registry

**English** · [Português](README.pt.md)

[Database design requirements](DATABASE_REQUIREMENTS.md)

Chemical reagent registration, search, and location system for laboratories, accessible through a local-network web interface and Telegram and WhatsApp bots.

> **Project status:** v0.0.1 early MVP. Telegram search is available; WhatsApp is a test integration with Meta test-number and messaging-window limits. OCR remains planned.

Product scope, bot capabilities and limitations, and inventory source/import dates: [v0.0.1 release notes (English)](docs/PRODUCT-v0.0.1.md) · [Português](docs/PRODUCT-v0.0.1.pt.md) · [Русский](docs/PRODUCT-v0.0.1.ru.md).

## Run locally

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
python -m pip install -r requirements-dev.txt
python manage.py migrate
python manage.py setup_roles
python manage.py runserver 8766
```

Open `http://127.0.0.1:8766/`. The technical administration interface is available at `/admin/`. Create its first administrator with `python manage.py createsuperuser`.

Local settings are loaded from `.env`. The supplied development file uses `DJANGO_ALLOWED_HOSTS=*`; copy `.env.example` when preparing another environment. Restart the Django server after changing environment variables.

This Windows workstation's network service: [local web setup](docs/LOCAL-WEB.md) · [Português](docs/LOCAL-WEB.pt.md) · [Русский](docs/LOCAL-WEB.ru.md).

To import or refresh an XLSX workbook:

```powershell
python manage.py import_inventory --source "C:\path\to\inventory.xlsx"
python manage.py import_sds_links --source "C:\path\to\inventory.xlsx"
```

The first command imports inventory rows and is idempotent for the same workbook checksum. The second command reads hyperlinks embedded in Excel cells and associates the actual SDS URLs with imported reagents. PostgreSQL is enabled when the `POSTGRES_*` environment variables shown in `.env.example` are set; otherwise local development uses SQLite.

## Telegram reagent search

Set `TELEGRAM_BOT_TOKEN` in `.env`, then start a separate worker:

```powershell
.\venv\Scripts\python.exe manage.py run_telegram_bot --check
.\venv\Scripts\python.exe manage.py run_telegram_bot
```

In a private chat with the bot, send `/start`, a reagent name, CAS, formula, manufacturer, catalogue reference or barcode. Multiple matches appear as buttons with pagination; selecting one displays the available packages and their laboratory/cabinet/shelf locations. One match displays its locations immediately. Written-off, missing, pending and reserved packages are excluded. Search matches text fragments, not spelling errors. Replies use PT/EN labels.

The worker uses the same Django search service and database as the website. It polls the [Telegram Bot API](https://core.telegram.org/bots/api#getupdates), so it needs outbound HTTPS but no public web port. Run only one worker per token. Stop it with Ctrl+C. Pagination expires after one hour or a worker restart. Empty `TELEGRAM_ALLOWED_USER_IDS` allows any Telegram user to search in private chats; groups are ignored. The bot cannot change inventory.

`SQLITE_PATH` in `.env` points to the existing SQLite database. SQLite has no server login/password. The optional `POSTGRES_*` settings select PostgreSQL only after real connection credentials and a data migration are provided. System environment variables take precedence over `.env`.

## WhatsApp reagent search

Set the `WHATSAPP_*` and `META_APP_SECRET` variables shown in `.env.example`, then configure the Meta webhook callback to `WHATSAPP_WEBHOOK_URL` and subscribe the app to the WABA `messages` field. Incoming text supports `/start`, `/help`, `/search`, `/pesquisar`, names, CAS numbers, formulas and manufacturers. Multiple matches appear as a WhatsApp list with selection and pagination; one match shows its available packages and locations immediately. Results include the SDS link when present. `/pt`, `/en` and `/auto` control voice recognition language. Voice search uses the same local model and 30-second / 5-MB limit as Telegram. Empty `WHATSAPP_ALLOWED_USER_IDS` allows any sender; otherwise enter comma-separated phone numbers. The bot only reads inventory. Search pages expire after one hour or a webhook process restart.

Security CI: [GitLab pipeline and policy](docs/SECURITY-CI.md) · [Português](docs/SECURITY-CI.pt.md) · [Русский](docs/SECURITY-CI.ru.md).

## Tests and lint

```powershell
.\venv\Scripts\python.exe -m pytest
.\venv\Scripts\python.exe -m ruff check .
.\venv\Scripts\python.exe -m ruff format --check .
.\venv\Scripts\python.exe manage.py check
```

Pytest uses an isolated test database and generates `coverage.xml`. Coverage excludes tests and migrations, with an 85% minimum. Tests cover permissions, stock operations and rollback, forms, pages, search, invalid query parameters, and local XLSX import without network access. If port 8766 is occupied, use `python manage.py runserver 127.0.0.1:8767`.

## Purpose

LabChem Registry centralizes the institution's chemical reagent inventory in a single application and database hosted on the internal network. Each container or physical unit is registered separately so that it can be found by its identity and storage location.

## Planned features

- Search by full or partial name, CAS number, manufacturer, catalogue reference, or laboratory.
- Physical location represented as **laboratory → cabinet → shelf**.
- Manual registration of new reagents.
- Registration from a label photograph, with preliminary data extraction.
- Mandatory review and correction of recognized data before saving.
- Record editing according to user permissions.
- Movement of reagents between storage locations.
- Retirement of consumed or unavailable units without deleting their records.
- Photo-based identification of an existing record before retirement.
- Audit history for relevant operations.
- Web, Telegram, and WhatsApp access through one shared backend.

The system does not track partial consumption or the remaining quantity in a container.

## Reagent record

Each physical unit will have its own record containing:

- name;
- CAS number, when available;
- manufacturer;
- catalogue reference or product number, when available;
- concentration, purity, or grade, when applicable;
- laboratory, cabinet, and shelf;
- label photograph;
- status;
- optional notes.

Required fields will be limited to the information needed to identify and locate the reagent.

## Essential rules

- Standard search results include available reagents only.
- Label recognition never creates a final record without human confirmation.
- During retirement, recognition searches for an existing unit rather than creating a new one.
- Retirement changes the unit's status while preserving its record and history.
- Database-changing operations are attributed to the responsible user.

## Users and permissions

Three initial roles are planned:

- **User:** search and permitted day-to-day operations.
- **Laboratory manager:** management of reagents and locations under their responsibility.
- **Administrator:** management of users, laboratories, and location reference data.

The final permission matrix will be defined during the design phase.

## Planned architecture

```text
Web interface ─┐
Telegram bot ──┼── Shared API/backend ── PostgreSQL on the internal network
WhatsApp bot ──┘          │
                          ├── label recognition
                          ├── authentication and authorization
                          └── operation history
```

The primary database must remain within the institution's internal infrastructure. Only the communication required by the Telegram and WhatsApp services will leave the internal network.

## Proposed delivery phases

1. Design the data model, API, users, and location hierarchy.
2. Implement the local database and backend.
3. Develop the local-network web interface.
4. Integrate the Telegram bot.
5. Implement photo-based label recognition.
6. Integrate the WhatsApp bot.
7. Test in real laboratory conditions, refine workflows, and deploy.

The architecture should support future internal identifiers and QR codes, although they are not mandatory for the first release.

## Local Telegram voice search (English / Portuguese)

One-time installation in the activated virtual environment:

```powershell
pip install -r requirements-voice.txt
python manage.py setup_voice
```

Set `TELEGRAM_VOICE_ENABLED=1` and `TELEGRAM_VOICE_MODEL=models/whisper-small` in `.env`,
then restart `python manage.py run_telegram_bot` (only one worker per token).
Send a voice message of up to 30 seconds / 5 MB in a private chat.
The bot displays the transcript, searches existing synonyms and shows matching reagents
and their locations. Say the reagent name, without a full question.
Use `/pt` or `/en` for short names; `/auto` restores language detection (default).
The language preference resets when the worker restarts.

Speech recognition uses a local multilingual faster-whisper model on CPU, not an external
transcription API. The initial model download needs internet; inference does not.
Telegram itself still requires internet and receives your voice messages. Audio is decoded
in memory, not saved to the database or disk. Text search does not use an LLM.
If recognition fails, send text; always check the displayed chemical name and CAS.
Voice processing is sequential and can delay other requests while a clip is processed.
The optional voice tests require `requirements-voice.txt`; run `pytest` and `ruff check .`.

## License status

No license has been defined yet.
