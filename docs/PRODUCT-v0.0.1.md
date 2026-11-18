# LabChem Registry v0.0.1

**Release date:** 18 November 2026  
**Status:** early MVP for internal inventory use

LabChem Registry is a Django application for locating and managing laboratory reagent stock. It stores reagent details separately from physical packages and their locations.

## Current functionality

- Search inventory by reagent name, formula, CAS number, supplier, catalogue number, or barcode. Filter by laboratory, source worksheet, location, and stock status; sort and paginate results.
- View reagent details, individual packages, available quantities, locations, expiry dates, SDS links, and stock movement history.
- Add a reagent and package; record package use, move a package, or write it off. Operations that change stock are recorded in the movement history and require the relevant Django permission.
- Browse the location tree, dashboard counts, and an attention list for low stock, pending or missing packages, missing locations or SDS links, and expiry dates within 90 days.
- Export inventory to XLSX and access a read-only JSON list at `/api/v1/reagents/` (up to 100 results per request).
- Manage users and permissions through Django administration. The configured groups are Viewer, Laboratory user, and Administrator.

The website, bots, and API use the same Django data store. The default local setup uses SQLite; PostgreSQL can be configured separately. This release does not include label OCR or automatic creation of records from photographs.

## Telegram bot

The Telegram bot is a read-only search interface backed by the same inventory. In private chats it accepts names, formulas, CAS numbers, suppliers, catalogue references, and barcodes. It shows available packages and locations, SDS links, and paginated buttons for multiple results. Groups are ignored. An optional Telegram user allowlist is supported.

Voice search is optional and requires the local speech model to be installed and enabled. English and Portuguese are supported; clips are limited to 30 seconds and 5 MB. Search pages expire after one hour or a worker restart. Run one long-polling worker per bot token.

## WhatsApp bot — test version

The WhatsApp integration uses Meta WhatsApp Cloud API with the Meta development app's test phone number. It replies to incoming text and audio messages, searches available inventory, and uses interactive lists for multi-result selection. It does not change inventory and does not send campaigns or start conversations on its own. Only recipient numbers added and verified for the Meta test setup can be used; production availability requires completing Meta's production onboarding and configuring a production number and credentials. Meta's API also restricts free-form replies to its customer-service messaging window; approved templates are required for business-initiated messages outside that window. See Meta's [Cloud API overview](https://developers.facebook.com/documentation/business-messaging/whatsapp/overview) and [template documentation](https://developers.facebook.com/docs/whatsapp/api/messages/message-templates/).

The webhook must be reachable by Meta and configured with the matching verification token and app secret. Incoming webhook signatures are checked and duplicate message IDs are ignored. Voice search is optional: it requires the local model, accepts English or Portuguese, and limits audio to 30 seconds and 5 MB. Text searches accept 2–200 characters; result pages expire after one hour or a webhook restart. The optional sender allowlist can restrict access further.

## Inventory source and date

The imported inventory came from the SharePoint workbook **`2026 Todos labs TEMA.xlsx`**. The source workbook was recorded as accessed on **21 September 2026** in the database requirements. The current database import batch is dated **16 November 2026 at 15:19 (Europe/Lisbon)** and records 1,225 imported rows and 69 skipped rows. The workbook contains an August 2026 gas-inventory sheet; the older April 2026 gas snapshot and a print-only vapour-cabinet sheet are excluded by the importer.

The original source workbook is not stored in this repository. `inventory/data/inventory_export_template.xlsx` is the local XLSX export template, not the source workbook. The database records the source filename, import time, checksum, and row counts. It does not record a separate workbook publication or last-modified date, so the source access date and database import date above are distinct facts.

The Git release identifier is `v0.0.1`.
