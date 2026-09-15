# LabChem Registry

**English** · [Português](README.pt.md)

Chemical reagent registration, search, and location system for laboratories, accessible through a local-network web interface and, in future phases, through Telegram and WhatsApp bots.

> **Project status:** Planning stage; implementation has not started yet.

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

## License

No license has been defined yet.
