# Local network web interface (Windows workstation)

The workstation's `TEMA LabChem Registry Web 8080` scheduled task runs `scripts/windows/run_registry_web_http.ps1` at sign-in. It binds to `0.0.0.0:8080`, so the application is available at `http://127.0.0.1:8080/` on the workstation and at `http://192.168.1.7:8080/` from reachable networks. The local Caddy HTTPS proxy is stopped; port 8080 uses HTTP.

The script uses `config.settings_local_http`, which keeps `DEBUG=False`, accepts Host headers for all addresses, and disables HTTPS redirects and secure-only cookies for this HTTP service. Django's `--insecure` option serves CSS and JavaScript with `DEBUG=False`. Do not use these settings for an internet-facing deployment.

To restart the task after changing the code or `.env`:

```powershell
Stop-ScheduledTask -TaskName 'TEMA LabChem Registry Web 8080'
Start-ScheduledTask -TaskName 'TEMA LabChem Registry Web 8080'
```

The service listens on all IPv4 interfaces, but Windows Firewall can still block inbound traffic. This workstation's Public profile accepts only group-policy rules. Direct HTTP traffic is unencrypted; do not expose this service to an untrusted network.
