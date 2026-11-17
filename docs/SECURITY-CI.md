# GitLab security pipeline

[Português](SECURITY-CI.pt.md) · [Русский](SECURITY-CI.ru.md)

The pipeline follows `E:\git_prog\xps-journal\.gitlab-ci.yml`. The project instructions were copied to `AGENTS.md` at the user's request.

Every branch push and merge request runs `.gitlab-ci.yml`; open merge requests suppress duplicate branch pipelines. Jobs use GitLab hosted Linux runners tagged `saas-linux-small-amd64`. No production credentials, database, SSH access or deployment are required. Docker-in-Docker builds a disposable image for scanning; the image is neither published nor deployed. The existing XPS S3 connectivity job is omitted because this project has no corresponding S3 requirement.

| Check | Purpose |
| --- | --- |
| Ruff | Python errors and unused imports |
| pytest | Inventory, Telegram, WhatsApp and local voice regression tests; minimum coverage 85% |
| Bandit | Python security analysis; version 1.9.4 supports Python 3.14 |
| Semgrep | Additional static analysis using `p/default` |
| TruffleHog | Verified secret detection across Git history (`GIT_DEPTH=0`) |
| pip-audit | Published vulnerabilities in `requirements.txt` |
| Trivy filesystem/config/image | Dependencies, secrets, configuration and the runtime image |
| Security gateway | Aggregate reports and enforce the policy below |

The gateway blocks verified secrets, Bandit HIGH findings or scanner errors, Trivy filesystem/image HIGH or CRITICAL findings, and missing or invalid required JSON reports. As in the reference project, pip-audit findings, Semgrep findings and Trivy configuration findings are reported for review. Scanner execution failures still fail their jobs. Reports are retained for one week; security artifact downloads require Developer access. Test reports are available as JUnit XML and coverage XML.

In GitLab, open **Build → Pipelines**, select the branch and inspect failed job logs. Download `security-gateway-report.md` and `.json` from `security:gateway` for the consolidated result. A push starts a pipeline; the API also supports `POST /projects/:id/pipeline` with a branch `ref`.

API automation uses a local, ignored `.env` variable `GITLAB_TOKEN` with `api` scope. Project access tokens can read jobs and pipeline reports according to their project role; CI Lint or runner administration may require Maintainer permissions. Never commit this token or add production WhatsApp/Meta credentials to CI. Token values are not printed. `.dockerignore` also excludes secrets, local databases, lab workbooks and voice models from build context.

Export tests generate a synthetic workbook in a temporary directory. The real `inventory/data/inventory_export_template.xlsx` stays local and ignored. CI installs optional voice dependencies, but never downloads the speech model or transcribes real audio. Pillow was upgraded from 12.3.0 to 13.0.0 following dependency audit recommendations.

Local checks with development-only environment overrides:

```powershell
$env:DJANGO_DEBUG = '1'
$env:DJANGO_ALLOWED_HOSTS = '*'
$env:DJANGO_SECRET_KEY = 'ci-only-ephemeral-key'
.\venv\Scripts\python.exe -m pytest -q
.\venv\Scripts\python.exe -m ruff check . --select E4,E7,E9,F
```

These overrides apply only to the current terminal; do not change the running site's production `.env` settings.
