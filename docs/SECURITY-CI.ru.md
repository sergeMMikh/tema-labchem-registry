# Проверки безопасности в GitLab

[English](SECURITY-CI.md) · [Português](SECURITY-CI.pt.md)

Pipeline создан по образцу `E:\git_prog\xps-journal\.gitlab-ci.yml`. По просьбе пользователя инструкции проекта скопированы в `AGENTS.md`.

`.gitlab-ci.yml` запускается при push ветки и merge request. Для открытого merge request повторный pipeline ветки отключается. Используются runners проекта: `build, docker` для lint, тестов и образа; `security, sast` для сканирования и gateway. Доступ к рабочей базе, SSH и секреты рабочего приложения не нужны. Docker-in-Docker собирает временный образ для проверки, без публикации и развёртывания. Проверка S3 из проекта XPS исключена: у этого проекта нет соответствующей задачи.

Pipeline включает Ruff, pytest с порогом покрытия 85%, совместимый с Python 3.14 Bandit 1.9.4, Semgrep (`p/default`), TruffleHog по полной истории Git, pip-audit, Trivy для файлов, конфигурации и Docker образа, а также итоговый security gateway.

Gateway блокирует подтверждённые секреты, находки HIGH и ошибки анализа Bandit, HIGH/CRITICAL Trivy для файлов и образа, отсутствие или некорректность обязательных JSON отчётов. Как в образце, находки pip-audit, Semgrep и Trivy config выводятся для рассмотрения. Ошибки выполнения самих scanners приводят к ошибке job. Артефакты хранятся неделю; скачивание security отчётов требует роли Developer. Для тестов публикуются JUnit XML и coverage XML.

В GitLab откройте **Build → Pipelines**, выберите ветку и изучите лог неуспешного job. Итоговые `security-gateway-report.md` и `.json` находятся в артефактах `security:gateway`. Push запускает pipeline автоматически; для API доступен `POST /projects/:id/pipeline` с именем ветки в `ref`.

Для автоматизации API используется `GITLAB_TOKEN` с правом `api` из локального игнорируемого `.env`. Доступ ограничен ролью токена в проекте; CI Lint и управление runners могут требовать Maintainer. Токен GitLab и рабочие WhatsApp/Meta секреты не должны попадать в CI. Их значения не выводятся. `.dockerignore` исключает секреты, базы, лабораторные Excel файлы и голосовые модели из Docker build context.

Тесты экспорта создают синтетический Excel во временном каталоге. Настоящий `inventory/data/inventory_export_template.xlsx` остаётся локальным и игнорируется Git. CI устанавливает зависимости голосового модуля, но не скачивает модель и не обрабатывает настоящее аудио. По результатам dependency audit Pillow обновлён с 12.3.0 до 13.0.0.

Для локального запуска задайте только в текущем терминале `DJANGO_DEBUG=1`, `DJANGO_ALLOWED_HOSTS=*` и временный `DJANGO_SECRET_KEY`, затем выполните `python -m pytest -q` и `python -m ruff check . --select E4,E7,E9,F`. Не меняйте рабочий `.env` ради тестов.
