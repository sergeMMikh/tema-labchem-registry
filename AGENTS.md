# TEMA XPS Journal — agent instructions

## Application languages

- The application interface must support English and Portuguese (Portugal).
- English is the default language. Provide a persistent EN / PT language switch.
- Translate all user-facing navigation, forms, validation, notifications, reports and administration labels. Keep operator names, customer names, sample names and source scientific documents unchanged.
- Use Django internationalization and maintain the Portuguese translation catalog.
- Display and accept calendar dates in European `DD/MM/YYYY` format throughout the application, including forms and selection labels. Do not rely on browser locale for date inputs.
- Enter times in 24-hour `HH:MM` format using separate hour and minute controls; users should not have to type a colon or seconds. Display timestamps in 24-hour format, including seconds when useful. Do not show AM/PM.

## Shared TEMA design

- Match the design of `E:\NRD-Soft\tema-labchem-registry`: shared TEMA colours, typography, header, sidebar, cards, tables and forms.
- Both applications belong to the same TEMA service.

## Experiment records

- `X:\` contains operator working directories; initially use their directory names as operator names.
- A directory containing spectra tables represents one sample. Customer names normally come from a directory inside an operator directory.
- Retain source paths, file creation and modification timestamps, and raw XY metadata.
- All direct sample folders inside one customer/experiment folder belong to one experiment and share its request form, even when acquisition continues on later days. Use the earliest actual sample acquisition as the experiment's displayed date; preserve each sample's own timestamps. Never override a manually entered experiment date during import. A standalone sample folder without a separate experiment parent remains its own experiment.
- Keep the operator-entered experiment start separate from acquisition timestamps and file export timestamps. Never infer a manually entered start.
- Preserve the last acquisition time and the last acquisition end only when it can be established from source metadata. By default, the experiment end date must match the operator-entered start date. When the operator changes the start date, update the end date too unless the operator explicitly chooses a different end date. The sample edit form may suggest an end time from the first XY file creation time, but must keep the end date equal to the start date by default. Never infer the manually entered start or set a confirmed end during import.
- Allow unknown sample names and customer departments to be completed later. Department usage statistics are a primary requirement.
- Support uploaded request scans and documents, including PDF and DOC files.
- Keep the working directory name as the import identity. The client name defaults to the same value, but may differ after editing or request-form recognition. OCR may fill missing client name, email and department. If its client name or email differs from a populated card field, show both values and require explicit confirmation before changing anything. OCR must never rename the working directory.
- Import is repeatable and must preserve operator edits. Never modify source files on X:.
- The new experiment page may create operator/customer/date folders and save uploaded request documents on X:. Keep existing XY/SLE instrument files unchanged.

## Element reference library

- Maintain experiment records and element references in separate databases.
- Save genuine Thermo Fisher XPS element pages as PDF, retaining source URLs and capture dates.
- Do not invent binding energies, scientific descriptions or missing source content. Missing elements can be added later.

## Interface change delivery

- After making application interface changes, create a git commit, push it to the configured remote, and restart the application. Confirm that the restart succeeded.

## Documentation formats

- Whenever a project documentation `.md` file is created or updated, create or update a matching `.html` file in the same directory with the same basename. The HTML file must contain the same documentation content, rendered as HTML, and stay synchronized with the Markdown version.
