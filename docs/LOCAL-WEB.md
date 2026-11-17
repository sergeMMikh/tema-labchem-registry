# Local network web interface (Windows workstation)

The workstation's `TEMA LabChem Registry Web 8080` scheduled task runs `scripts/windows/run_registry_web_http.ps1` at sign-in. It serves the application directly at `http://192.168.1.7:8080/`. The old local Caddy HTTPS proxy is stopped; port 8080 uses HTTP.

The script uses `config.settings_local_http`, which keeps `DEBUG=False` while disabling HTTPS redirects and secure-only cookies for this local HTTP service. Django's `--insecure` option serves CSS and JavaScript with `DEBUG=False`. Do not use these settings for an internet-facing deployment.

To restart the task after changing the code or `.env`:

```powershell
Stop-ScheduledTask -TaskName 'TEMA LabChem Registry Web 8080'
Start-ScheduledTask -TaskName 'TEMA LabChem Registry Web 8080'
```

The service listens only on the workstation's `192.168.1.7` interface. If its IP changes, update the bind address in the script. Access from other computers also depends on the network's Windows Firewall policy; this workstation's Public profile accepts only group-policy rules.
