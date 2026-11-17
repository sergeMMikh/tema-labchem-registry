# Interface web na rede local (estação Windows)

A tarefa agendada `TEMA LabChem Registry Web 8080` executa `scripts/windows/run_registry_web_http.ps1` ao iniciar sessão. A aplicação está disponível diretamente em `http://192.168.1.7:8080/`. O proxy HTTPS local Caddy foi parado; a porta 8080 usa HTTP.

O script utiliza `config.settings_local_http`, que mantém `DEBUG=False` e desativa o redirecionamento HTTPS e os cookies exclusivos de HTTPS neste serviço HTTP local. A opção `--insecure` do Django disponibiliza CSS e JavaScript com `DEBUG=False`. Não utilize estas definições numa instalação exposta à Internet.

Para reiniciar a tarefa após alterar o código ou `.env`:

```powershell
Stop-ScheduledTask -TaskName 'TEMA LabChem Registry Web 8080'
Start-ScheduledTask -TaskName 'TEMA LabChem Registry Web 8080'
```

O serviço escuta apenas na interface `192.168.1.7` da estação. Se o endereço mudar, atualize-o no script. O acesso a partir de outros computadores depende também da política do Windows Firewall; o perfil Public desta estação só aceita regras definidas por política de grupo.
