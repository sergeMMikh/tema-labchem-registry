# Pipeline de segurança no GitLab

[English](SECURITY-CI.md) · [Русский](SECURITY-CI.ru.md)

O pipeline segue `E:\git_prog\xps-journal\.gitlab-ci.yml`. As instruções desse projeto foram copiadas para `AGENTS.md` a pedido do utilizador.

Cada push de um ramo e cada merge request executam `.gitlab-ci.yml`. Os merge requests abertos evitam pipelines duplicados. São utilizados runners do projeto: `build, docker` para lint/testes/imagem e `security, sast` para seguran?a e gateway. Não são necessárias credenciais de produção, base de dados, SSH ou implementação. Docker-in-Docker constrói uma imagem temporária para análise, sem publicação nem implementação. A verificação S3 do projeto XPS não se aplica a este projeto.

O pipeline executa Ruff, pytest com cobertura mínima de 85%, Bandit 1.9.4 compatível com Python 3.14, Semgrep (`p/default`), TruffleHog sobre todo o histórico Git, pip-audit e Trivy para ficheiros, configuração e imagem. O gateway reúne os relatórios de segurança.

O gateway bloqueia segredos verificados, resultados HIGH ou erros de análise do Bandit, resultados HIGH ou CRITICAL do Trivy para ficheiros/imagem e relatórios JSON obrigatórios em falta ou inválidos. Tal como no projeto de referência, os resultados pip-audit, Semgrep e Trivy de configuração são apresentados para revisão. Falhas de execução das ferramentas continuam a falhar o respetivo job. Os artefactos são guardados durante uma semana; o acesso aos relatórios de segurança exige o papel Developer. Os testes publicam JUnit XML e coverage XML.

No GitLab, abra **Build → Pipelines**, selecione o ramo e consulte os logs dos jobs com falha. Descarregue `security-gateway-report.md` e `.json` do job `security:gateway`. Um push inicia o pipeline; também é possível usar `POST /projects/:id/pipeline` com o ramo em `ref`.

A automação API utiliza `GITLAB_TOKEN` com âmbito `api` no `.env` local ignorado pelo Git. O acesso depende do papel do token no projeto; CI Lint e administração de runners podem exigir Maintainer. Nunca inclua esse token nem credenciais WhatsApp/Meta de produção no CI. Os valores dos tokens não são impressos. `.dockerignore` exclui segredos, bases locais, folhas laboratoriais e modelos de voz do contexto Docker.

Os testes de exportação criam um Excel sintético numa pasta temporária; o ficheiro real `inventory/data/inventory_export_template.xlsx` permanece local e ignorado. O CI instala as dependências opcionais de voz sem descarregar o modelo nem processar áudio real. Pillow foi atualizado de 12.3.0 para 13.0.0 após a auditoria de dependências.

Para verificações locais, use `DJANGO_DEBUG=1`, `DJANGO_ALLOWED_HOSTS=*` e uma `DJANGO_SECRET_KEY` temporária apenas no terminal; execute `python -m pytest -q` e `python -m ruff check . --select E4,E7,E9,F`. Não altere o `.env` de produção para executar os testes.
