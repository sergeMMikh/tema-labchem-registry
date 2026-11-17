# Веб-интерфейс в локальной сети (Windows)

Задание Windows `TEMA LabChem Registry Web 8080` при входе в систему запускает `scripts/windows/run_registry_web_http.ps1`. Сервер слушает `0.0.0.0:8080`: на этом компьютере открывайте `http://127.0.0.1:8080/`, а из доступных сетей — `http://192.168.1.7:8080/`. Локальный HTTPS-прокси Caddy остановлен; порт 8080 работает по HTTP.

Скрипт использует `config.settings_local_http`: `DEBUG=False` сохраняется, адреса в заголовке Host принимаются без ограничений, а перенаправление на HTTPS и требование HTTPS для cookie отключены только для этого HTTP-сервиса. Параметр Django `--insecure` отдаёт CSS и JavaScript при `DEBUG=False`. Эти настройки не предназначены для публикации приложения в интернете.

После изменения кода или `.env` перезапустите задание:

```powershell
Stop-ScheduledTask -TaskName 'TEMA LabChem Registry Web 8080'
Start-ScheduledTask -TaskName 'TEMA LabChem Registry Web 8080'
```

Сервер слушает все IPv4-интерфейсы, но Windows Firewall может блокировать входящие соединения. Для профиля Public на этой машине действуют только правила групповой политики. HTTP-трафик не шифруется; не открывайте этот сервис в недоверенных сетях.
