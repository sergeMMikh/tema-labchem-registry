# Interface web na rede local (estação Windows)

A tarefa agendada `TEMA LabChem Registry Web 8080` executa `scripts/windows/run_registry_web_http.ps1` ao iniciar sessão. O serviço escuta em `0.0.0.0:8080`: na própria estação, utilize `http://127.0.0.1:8080/`; nas redes alcançáveis, utilize `http://192.168.1.7:8080/`. O proxy HTTPS local Caddy foi parado; a porta 8080 usa HTTP.

O script utiliza `config.settings_local_http`, que mantém `DEBUG=False`, aceita cabeçalhos Host para todos os endereços e desativa o redirecionamento HTTPS e os cookies exclusivos de HTTPS neste serviço HTTP. A opção `--insecure` do Django disponibiliza CSS e JavaScript com `DEBUG=False`. Não utilize estas definições numa instalação exposta à Internet.

Para reiniciar a tarefa após alterar o código ou `.env`:

```powershell
Stop-ScheduledTask -TaskName 'TEMA LabChem Registry Web 8080'
Start-ScheduledTask -TaskName 'TEMA LabChem Registry Web 8080'
```

O serviço escuta em todas as interfaces IPv4, mas o Windows Firewall pode bloquear ligações de entrada. O perfil Public desta estação só aceita regras definidas por política de grupo. O tráfego HTTP não é cifrado; não exponha este serviço a redes não fidedignas.

Se o Firefox mostrar `SSL_ERROR_RX_RECORD_TOO_LONG` na porta 8080, está a tentar HTTPS num serviço HTTP. Introduza o endereço completo `http://127.0.0.1:8080/`. Se o Firefox continuar a atualizar a ligação, abra **Definições → Privacidade e Segurança → Modo apenas HTTPS → Gerir exceções**, adicione `http://127.0.0.1:8080/`, escolha **Desativar** e guarde. Adicione o endereço da rede separadamente, se necessário. O modo HTTPS-First também respeita estas exceções.
