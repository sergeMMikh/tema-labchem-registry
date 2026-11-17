# Веб-интерфейс в локальной сети (Windows)

Задание Windows `TEMA LabChem Registry Web 8080` при входе в систему запускает `scripts/windows/run_registry_web_http.ps1`. Приложение доступно напрямую по адресу `http://192.168.1.7:8080/`. Локальный HTTPS-прокси Caddy остановлен; порт 8080 работает по HTTP.

Скрипт использует `config.settings_local_http`: `DEBUG=False` сохраняется, а перенаправление на HTTPS и требование HTTPS для cookie отключены только для этого локального HTTP-сервиса. Параметр Django `--insecure` отдаёт CSS и JavaScript при `DEBUG=False`. Эти настройки не предназначены для публикации приложения в интернете.

После изменения кода или `.env` перезапустите задание:

```powershell
Stop-ScheduledTask -TaskName 'TEMA LabChem Registry Web 8080'
Start-ScheduledTask -TaskName 'TEMA LabChem Registry Web 8080'
```

Сервер слушает только интерфейс `192.168.1.7`. Если адрес изменится, обновите его в скрипте. Доступ с других компьютеров также зависит от политики Windows Firewall: для профиля Public на этой машине действуют только правила групповой политики.
