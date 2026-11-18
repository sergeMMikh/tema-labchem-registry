"""WhatsApp Cloud API search and confirmed photo registration."""

import json
import re
import urllib.error
import urllib.parse
import urllib.request
from uuid import UUID

from django.conf import settings
from django.core import signing
from django.core.cache import cache

from .bot_save import (
    cancel_save,
    pending_save,
    save_name,
    save_photo_reagent,
    start_save,
    storage_locations,
)
from .photo_lookup import (
    MAX_PHOTO_BYTES,
    PhotoLookupError,
    describe_label,
    describe_sigma,
    identify_label,
    inventory_match,
    sigma_lookup,
)
from .search import search_reagents
from .voice import MAX_VOICE_BYTES, VoiceError, transcribe

PAGE_SIZE = 8


class WhatsAppError(Exception):
    def __init__(self, code=0):
        self.code = code
        super().__init__(f"WhatsApp request failed (code {code})")


class WhatsAppClient:
    def __init__(self, token=None, phone_number_id=None, version=None):
        self.token = token if token is not None else settings.WHATSAPP_ACCESS_TOKEN
        self.phone_number_id = (
            phone_number_id if phone_number_id is not None else settings.WHATSAPP_PHONE_NUMBER_ID
        )
        self.version = version if version is not None else settings.WHATSAPP_API_VERSION
        if not self.token or not self.phone_number_id:
            raise WhatsAppError()

    def _open(self, request, limit=None):
        try:
            with urllib.request.urlopen(request, timeout=8) as response:
                return response.read(limit) if limit else response.read()
        except urllib.error.HTTPError as exc:
            code = exc.code
            exc.close()
            raise WhatsAppError(code) from None
        except (OSError, ValueError):
            raise WhatsAppError() from None

    def send(self, recipient, body):
        payload = {"messaging_product": "whatsapp", "to": recipient, **body}
        request = urllib.request.Request(
            f"https://graph.facebook.com/{self.version}/{self.phone_number_id}/messages",
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.token}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            return json.loads(self._open(request))
        except (ValueError, TypeError):
            raise WhatsAppError() from None

    def text(self, recipient, body):
        return self.send(recipient, {"type": "text", "text": {"body": body}})

    def list(self, recipient, body, rows):
        return self.send(
            recipient,
            {
                "type": "interactive",
                "interactive": {
                    "type": "list",
                    "body": {"text": body},
                    "action": {
                        "button": "Selecionar",
                        "sections": [{"title": "Resultados", "rows": rows}],
                    },
                },
            },
        )

    def buttons(self, recipient, body, buttons):
        return self.send(recipient, {
            "type": "interactive",
            "interactive": {
                "type": "button", "body": {"text": body},
                "action": {"buttons": [{"type": "reply", "reply": item} for item in buttons]},
            },
        })

    def download_audio(self, media_id):
        return self._download_media(media_id, MAX_VOICE_BYTES)

    def download_image(self, media_id):
        return self._download_media(media_id, MAX_PHOTO_BYTES)

    def _download_media(self, media_id, limit):
        if not re.fullmatch(r"[0-9]{1,30}", str(media_id)):
            raise VoiceError("Invalid audio ID")
        url = f"https://graph.facebook.com/{self.version}/{media_id}"
        query = urllib.parse.urlencode({"phone_number_id": self.phone_number_id})
        request = urllib.request.Request(
            f"{url}?{query}", headers={"Authorization": f"Bearer {self.token}"}
        )
        try:
            metadata = json.loads(self._open(request))
            if int(metadata.get("file_size", 0)) > limit:
                raise VoiceError("Oversized audio")
            media_url = metadata["url"]
            parsed = urllib.parse.urlparse(media_url)
            host = (parsed.hostname or "").lower()
            allowed = ("facebook.com", "fbcdn.net", "fbsbx.com", "whatsapp.net")
            if parsed.scheme != "https" or not any(
                host == domain or host.endswith("." + domain) for domain in allowed
            ):
                raise VoiceError("Unexpected audio URL")
            media_request = urllib.request.Request(
                media_url, headers={"Authorization": f"Bearer {self.token}"}
            )
            audio = self._open(media_request, limit + 1)
        except (WhatsAppError, KeyError, ValueError, TypeError):
            raise VoiceError("Could not download audio") from None
        if not audio or len(audio) > limit:
            raise VoiceError("Empty or oversized audio")
        return audio


class WhatsAppBot:
    def __init__(self, client):
        self.client = client

    def handle(self, message):
        sender = str(message.get("from", ""))
        if not re.fullmatch(r"[0-9]{6,20}", sender):
            return
        if settings.WHATSAPP_ALLOWED_USER_IDS and sender not in settings.WHATSAPP_ALLOWED_USER_IDS:
            self.client.text(sender, "Acesso não autorizado / Access not authorized.")
            return
        interactive = message.get("interactive") or {}
        selection = (interactive.get("list_reply") or interactive.get("button_reply") or {}).get("id")
        selection = selection or (message.get("button") or {}).get("payload")
        if selection:
            self.selection(sender, selection)
            return
        if message.get("type") == "image" and message.get("image", {}).get("id"):
            self.photo(sender, message["image"]["id"])
            return
        if message.get("type") == "audio" and message.get("audio", {}).get("id"):
            self.voice(sender, message["audio"]["id"])
            return
        text = (message.get("text") or {}).get("body", "").strip()
        command = text.split(" ", 1)[0].lower()
        if command in ("/pt", "/en", "/auto"):
            cache.set(f"wa:language:{sender}", command[1:], timeout=None)
            self.client.text(sender, f"Idioma de voz / Voice language: {command[1:]}")
            return
        if command in ("/start", "/help") or not text:
            self.client.text(
                sender,
                "TEMA Reagents\nEnvie o nome, CAS, fórmula ou fabricante.\n"
                "Send a reagent name, CAS, formula or manufacturer.\n"
                "Ex.: acetone / 67-64-1\nVoz / Voice (PT/EN): max. 30 s. /pt /en /auto\n"
                "Foto da etiqueta / Label photo: inventory first, then Sigma-Aldrich.",
            )
            return
        if command in ("/search", "/pesquisar"):
            text = text.partition(" ")[2].strip()
        self.search(sender, text)

    def voice(self, sender, media_id):
        if not settings.WHATSAPP_VOICE_ENABLED:
            self.client.text(sender, "Voz desativada. Envie texto. / Voice disabled. Send text.")
            return
        self.client.text(sender, "A transcrever localmente… / Transcribing locally…")
        try:
            audio = self.client.download_audio(media_id)
            language = cache.get(f"wa:language:{sender}", "auto")
            text = transcribe(audio, language if language in ("pt", "en") else None)
        except (VoiceError, WhatsAppError):
            self.client.text(
                sender,
                "Não foi possível reconhecer. Tente /pt ou /en, ou envie texto. / "
                "Could not recognize speech. Try /pt or /en, or send text.",
            )
            return
        self.client.text(sender, f"Ouvi / Heard: {text}")
        self.search(sender, text)

    def photo(self, sender, media_id):
        try:
            photo = self.client.download_image(media_id)
            fields = identify_label(photo)
        except (PhotoLookupError, VoiceError, WhatsAppError):
            self.client.text(sender, "Não consegui ler a etiqueta / Could not read the label. Send a clearer photo.")
            return
        description = describe_label(fields)
        if not description:
            self.client.text(sender, "Etiqueta ilegível / Label unreadable. Send a clearer photo.")
            return
        reagent = inventory_match(fields)
        self.client.text(sender, "Etiqueta / Label:\n" + description)
        if reagent:
            self.client.text(sender, "Encontrado no inventário / Found in inventory:")
            self.locations(sender, reagent)
            return
        external = sigma_lookup(fields)
        self.client.text(sender, "Não encontrado no inventário / Not found in inventory.\n"
                         + describe_sigma(external))
        if not save_name(fields):
            self.client.text(sender, "Identidade insuficiente para guardar / Need a clearer label to save.")
            return
        allowed = settings.WHATSAPP_SAVE_USER_IDS
        if allowed and sender not in allowed:
            return
        key = start_save("wa", sender, fields, (external or {}).get("source_url", ""))
        self.client.buttons(sender, "Guardar este reagente? / Save this reagent?\n"
                            "Quantity will need review.", [
            {"id": f"save:{key}", "title": "Sim / Yes"},
            {"id": f"no:{key}", "title": "Não / No"},
        ])

    def save_locations(self, sender, key, page):
        if not pending_save("wa", sender, key):
            self.client.text(sender, "Pedido expirado / Request expired. Send the photo again.")
            return
        locations = storage_locations()
        if not locations:
            self.client.text(sender, "Sem locais disponíveis / No available locations.")
            return
        page = min(max(page, 0), (len(locations) - 1) // PAGE_SIZE)
        rows = [{"id": f"place:{key}:{loc.pk}", "title": loc.full_path[:24],
                 "description": loc.full_path[:72]}
                for loc in locations[page * PAGE_SIZE:(page + 1) * PAGE_SIZE]]
        if page:
            rows.append({"id": f"loc:{key}:{page - 1}", "title": "← Anterior"})
        if (page + 1) * PAGE_SIZE < len(locations):
            rows.append({"id": f"loc:{key}:{page + 1}", "title": "Próxima →"})
        self.client.list(sender, "Escolha a localização / Choose a location:", rows)

    def search(self, sender, text):
        if len(text) < 2 or len(text) > 200 or text.startswith("/"):
            self.client.text(sender, "Pesquisa: 2–200 caracteres / Search: 2–200 characters.")
            return
        key = signing.Signer(salt="whatsapp-search").signature(f"{sender}:{text}")[:16]
        cache.set(f"wa:search:{sender}:{key}", text, timeout=3600)
        self.results(sender, text, key, 0)

    def results(self, sender, query, key, page):
        results = search_reagents(query, available_only=True)
        count = results.count()
        if not count:
            self.client.text(sender, "Nenhum reagente disponível encontrado. / No available reagent found.")
            return
        if count == 1:
            self.locations(sender, results.first())
            return
        page = min(max(page, 0), (count - 1) // PAGE_SIZE)
        items = results[page * PAGE_SIZE : (page + 1) * PAGE_SIZE]
        rows = [
            {
                "id": f"r:{reagent.pk}",
                "title": reagent.name[:24],
                "description": f"CAS: {reagent.cas_number or '—'}"[:72],
            }
            for reagent in items
        ]
        if page:
            rows.append({"id": f"p:{key}:{page - 1}", "title": "← Anterior"})
        if (page + 1) * PAGE_SIZE < count:
            rows.append({"id": f"p:{key}:{page + 1}", "title": "Próxima →"})
        self.client.list(
            sender,
            f"{count} resultados / results — {page + 1}/{(count - 1) // PAGE_SIZE + 1}\n"
            "Selecione um reagente / Select a reagent:",
            rows,
        )

    def selection(self, sender, data):
        if data.startswith(("save:", "no:", "loc:", "place:")):
            parts = data.split(":")
            key = parts[1] if len(parts) >= 2 else ""
            if not pending_save("wa", sender, key):
                self.client.text(sender, "Pedido expirado / Request expired. Send the photo again.")
                return
            if parts[0] == "no" and len(parts) == 2:
                cancel_save("wa", sender, key)
                self.client.text(sender, "Não guardado / Not saved.")
            elif parts[0] == "save" and len(parts) == 2:
                self.save_locations(sender, key, 0)
            elif parts[0] == "loc" and len(parts) == 3 and parts[2].isdigit():
                self.save_locations(sender, key, int(parts[2][:6]))
            elif parts[0] == "place" and len(parts) == 3:
                result = save_photo_reagent("wa", sender, key, parts[2])
                if result:
                    reagent, created = result
                    self.client.text(sender, "Guardado / Saved (pending review):" if created else
                                     "Já existe no inventário / Already in inventory:")
                    self.locations(sender, reagent)
                else:
                    self.client.text(sender, "Local inválido ou pedido expirado / Invalid location or expired request.")
            else:
                self.client.text(sender, "Seleção inválida / Invalid selection.")
        elif data.startswith("r:"):
            try:
                reagent_id = UUID(data[2:])
            except ValueError:
                self.client.text(sender, "Seleção inválida / Invalid selection.")
                return
            reagent = search_reagents("", available_only=True).filter(pk=reagent_id).first()
            if reagent:
                self.locations(sender, reagent)
            else:
                self.client.text(sender, "Reagente indisponível / Reagent no longer available.")
        elif data.startswith("p:"):
            parts = data.split(":")
            query = cache.get(f"wa:search:{sender}:{parts[1]}") if len(parts) == 3 else None
            if not query or not parts[2].isdigit() or len(parts[2]) > 6:
                self.client.text(sender, "Pesquisa expirada. Envie novamente. / Search expired. Search again.")
                return
            self.results(sender, query, parts[1], int(parts[2]))
        else:
            self.client.text(sender, "Seleção inválida / Invalid selection.")

    def locations(self, sender, reagent):
        lines = [
            reagent.name,
            f"CAS: {reagent.cas_number or '—'}",
            f"Fabricante / Manufacturer: {reagent.supplier or '—'}",
            "\nLocalizações / Locations:",
        ]
        for package in reagent.packages.all():
            path = package.location.full_path if package.location else "Desconhecida / Unknown"
            lines.append(f"• {path}\n  {package.display_quantity} · #{str(package.pk)[:8]}")
        if reagent.sds_url:
            lines.append(f"\nSDS: {reagent.sds_url}")
        text = "\n".join(lines)
        while text:
            part, text = text[:1900], text[1900:]
            self.client.text(sender, part)
