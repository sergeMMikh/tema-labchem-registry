"""Telegram inventory search and confirmed photo registration."""

import json
import re
import urllib.error
import urllib.request
from uuid import UUID

from django.conf import settings
from django.core import signing
from django.core.cache import cache

from .bot_registration import NOT_FOUND, BotRegistration, clear_miss, note_miss
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
from .voice import MAX_VOICE_BYTES, MAX_VOICE_SECONDS, VoiceError, transcribe

PAGE_SIZE = 8


class TelegramError(Exception):
    def __init__(self, code=0, retry_after=5):
        self.code = code
        self.retry_after = min(max(int(retry_after), 1), 60)
        super().__init__(f"Telegram request failed (code {code})")


class TelegramClient:
    def __init__(self, token):
        if not token:
            raise ValueError("TELEGRAM_BOT_TOKEN is missing from .env")
        self._token = token

    def download_voice(self, file_id):
        return self._download_file(file_id, MAX_VOICE_BYTES)

    def download_photo(self, file_id):
        return self._download_file(file_id, MAX_PHOTO_BYTES)

    def _download_file(self, file_id, limit):
        file = self.call("getFile", file_id=file_id)
        path = file.get("file_path", "")
        if (
            not re.fullmatch(r"[A-Za-z0-9_/-]+\.[A-Za-z0-9]+", path)
            or ".." in path
            or path.startswith("/")
            or file.get("file_size", 0) > limit
        ):
            raise VoiceError("Invalid or oversized voice file")
        try:
            with urllib.request.urlopen(
                f"https://api.telegram.org/file/bot{self._token}/{path}", timeout=40
            ) as response:
                audio = response.read(limit + 1)
        except OSError, ValueError:
            raise VoiceError("Could not download voice") from None
        if not audio or len(audio) > limit:
            raise VoiceError("Empty or oversized voice file")
        return audio

    def call(self, method, **payload):
        request = urllib.request.Request(
            f"https://api.telegram.org/bot{self._token}/{method}",
            data=json.dumps(payload).encode(),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=40) as response:
                result = json.load(response)
        except urllib.error.HTTPError as exc:
            try:
                result = json.loads(exc.read())
            except ValueError, OSError:
                result = {}
            raise TelegramError(
                exc.code, result.get("parameters", {}).get("retry_after", 5)
            ) from None
        except OSError, ValueError:
            # Never surface an exception containing the token-bearing request URL.
            raise TelegramError() from None
        if not result.get("ok"):
            raise TelegramError(result.get("error_code", 0))
        return result["result"]


class ReagentBot:
    def __init__(self, client):
        self.client = client

    def send(self, chat_id, text, **kwargs):
        return self.client.call(
            "sendMessage",
            chat_id=chat_id,
            text=text,
            link_preview_options={"is_disabled": True},
            **kwargs,
        )

    def handle(self, update):
        callback = update.get("callback_query")
        message = callback.get("message", {}) if callback else update.get("message", {})
        chat = message.get("chat", {})
        user = (callback or message).get("from", {})
        if callback:
            self.client.call("answerCallbackQuery", callback_query_id=callback["id"])
        if chat.get("type") != "private" or not user.get("id"):
            return
        chat_id = chat["id"]
        allowed = settings.TELEGRAM_ALLOWED_USER_IDS
        if allowed and user["id"] not in allowed:
            self.send(chat_id, "Acesso não autorizado / Access not authorized.")
            return
        if callback:
            self.selection(chat_id, user["id"], callback.get("data", ""))
            return
        if message.get("photo"):
            self.photo(chat_id, user["id"], message["photo"])
            return
        if "voice" in message:
            self.voice(chat_id, user["id"], message["voice"])
            return
        text = message.get("text", "").strip()
        command = text.split(" ", 1)[0].split("@", 1)[0].lower()
        if command in ("/pt", "/en", "/auto"):
            cache.set(f"tg:language:{chat_id}:{user['id']}", command[1:], timeout=None)
            self.send(chat_id, f"Idioma de voz / Voice language: {command[1:]}")
            return
        if command in ("/start", "/help") or not text:
            self.send(
                chat_id,
                "TEMA Reagents\nEnvie o nome, CAS, fórmula ou fabricante.\n"
                "Send a reagent name, CAS, formula or manufacturer.\nEx.: acetone / 67-64-1\n"
                "Voz / Voice (PT/EN): max. 30 s. /pt /en /auto\n"
                "Foto da etiqueta / Label photo: inventory first, then Sigma-Aldrich.",
            )
            return
        if command in ("/search", "/pesquisar"):
            text = text.partition(" ")[2].strip()
        elif self.registration(chat_id, user["id"]).handle(text):
            return
        self.search(chat_id, user["id"], text)

    def registration(self, chat_id, user_id):
        allowed = settings.TELEGRAM_SAVE_USER_IDS
        return BotRegistration(
            "tg", f"{chat_id}:{user_id}", lambda text: self.send(chat_id, text),
            can_save=not allowed or user_id in allowed,
            offer_photo=lambda fields, source: self.offer_photo_save(chat_id, user_id, fields, source),
        )

    def voice(self, chat_id, user_id, voice):
        if not settings.TELEGRAM_VOICE_ENABLED:
            self.send(chat_id, "Voz desativada. Envie texto. / Voice disabled. Send text.")
            return
        if (
            voice.get("duration", 0) > MAX_VOICE_SECONDS
            or voice.get("file_size", 0) > MAX_VOICE_BYTES
            or not voice.get("file_id")
        ):
            self.send(chat_id, "Voz: máximo 30 s / Voice: maximum 30 s (5 MB).")
            return
        self.send(chat_id, "A transcrever localmente… / Transcribing locally…")
        try:
            audio = self.client.download_voice(voice["file_id"])
            language = cache.get(f"tg:language:{chat_id}:{user_id}", "auto")
            text = transcribe(audio, language if language in ("en", "pt") else None)
        except VoiceError, TelegramError:
            self.send(
                chat_id,
                "Não foi possível reconhecer. Tente /pt ou /en, ou envie texto. / "
                "Could not recognize speech. Try /pt or /en, or send text.",
            )
            return
        self.send(chat_id, f"Ouvi / Heard: {text}")
        self.search(chat_id, user_id, text)

    def photo(self, chat_id, user_id, photos):
        selected = photos[-1]
        if selected.get("file_size", 0) > MAX_PHOTO_BYTES or not selected.get("file_id"):
            self.send(chat_id, "Foto demasiado grande / Photo too large (10 MB).")
            return
        try:
            photo = self.client.download_photo(selected["file_id"])
            fields = identify_label(photo)
        except (PhotoLookupError, VoiceError, TelegramError):
            self.send(chat_id, "Não consegui ler a etiqueta / Could not read the label. Send a clearer photo.")
            return
        description = describe_label(fields)
        if not description:
            self.send(chat_id, "Etiqueta ilegível / Label unreadable. Send a clearer photo.")
            return
        reagent = inventory_match(fields)
        self.send(chat_id, "Etiqueta / Label:\n" + description)
        owner = f"{chat_id}:{user_id}"
        if reagent:
            clear_miss("tg", owner)
            self.send(chat_id, "Encontrado no inventário / Found in inventory:")
            self.locations(chat_id, reagent)
            return
        external = sigma_lookup(fields)
        note_miss("tg", owner, photo=(fields, (external or {}).get("source_url", "")))
        self.send(chat_id, "Não encontrado no inventário / Not found in inventory.\n"
                  + describe_sigma(external))

    def offer_photo_save(self, chat_id, user_id, fields, source_url):
        if not save_name(fields):
            self.send(chat_id, "Identidade insuficiente para guardar / Need a clearer label to save.")
            return
        key = start_save("tg", f"{chat_id}:{user_id}", fields, source_url)
        self.send(
            chat_id,
            "Guardar este reagente? / Save this reagent?\n"
            "A quantidade ficará por verificar / Quantity will need review.",
            reply_markup={"inline_keyboard": [[
                {"text": "Sim / Yes", "callback_data": f"save:{key}"},
                {"text": "Não / No", "callback_data": f"no:{key}"},
            ]]},
        )

    def save_locations(self, chat_id, user_id, key, page):
        if not pending_save("tg", f"{chat_id}:{user_id}", key):
            self.send(chat_id, "Pedido expirado / Request expired. Send the photo again.")
            return
        locations = storage_locations()
        if not locations:
            self.send(chat_id, "Sem locais disponíveis / No available locations.")
            return
        page = min(max(page, 0), (len(locations) - 1) // PAGE_SIZE)
        buttons = [[{"text": loc.full_path[:65], "callback_data": f"place:{key}:{loc.pk}"}]
                   for loc in locations[page * PAGE_SIZE:(page + 1) * PAGE_SIZE]]
        navigation = []
        if page:
            navigation.append({"text": "←", "callback_data": f"loc:{key}:{page - 1}"})
        if (page + 1) * PAGE_SIZE < len(locations):
            navigation.append({"text": "→", "callback_data": f"loc:{key}:{page + 1}"})
        if navigation:
            buttons.append(navigation)
        self.send(chat_id, "Escolha a localização / Choose a location:",
                  reply_markup={"inline_keyboard": buttons})

    def search(self, chat_id, user_id, text):
        if len(text) < 2 or len(text) > 200 or text.startswith("/"):
            self.send(chat_id, "Pesquisa: 2–200 caracteres / Search: 2–200 characters.")
            return
        # The short key fits Telegram's 64-byte callback limit; scope it to the user/chat.
        key = signing.Signer(salt="telegram-search").signature(f"{chat_id}:{user_id}:{text}")[:16]
        cache.set(f"tg:{chat_id}:{user_id}:{key}", text, timeout=3600)
        self.results(chat_id, text, key, 0, owner=f"{chat_id}:{user_id}")

    def results(self, chat_id, query, key, page, *, owner=None):
        results = search_reagents(query, available_only=True)
        count = results.count()
        if owner is not None:
            clear_miss("tg", owner)
        if not count:
            if owner is not None and not search_reagents(query).exists():
                note_miss("tg", owner)
                self.send(chat_id, NOT_FOUND)
                return
            self.send(
                chat_id, "Nenhum reagente disponível encontrado. / No available reagent found."
            )
            return
        if count == 1:
            self.locations(chat_id, results.first())
            return
        page = min(max(page, 0), (count - 1) // PAGE_SIZE)
        items = results[page * PAGE_SIZE : (page + 1) * PAGE_SIZE]
        buttons = [
            [{"text": f"{r.name[:65]} | {r.cas_number or 'CAS —'}", "callback_data": f"r:{r.pk}"}]
            for r in items
        ]
        navigation = []
        if page:
            navigation.append({"text": "←", "callback_data": f"p:{key}:{page - 1}"})
        if (page + 1) * PAGE_SIZE < count:
            navigation.append({"text": "→", "callback_data": f"p:{key}:{page + 1}"})
        if navigation:
            buttons.append(navigation)
        self.send(
            chat_id,
            f"{count} resultados / results — {page + 1}/{(count - 1) // PAGE_SIZE + 1}\n"
            "Selecione um reagente / Select a reagent:",
            reply_markup={"inline_keyboard": buttons},
        )

    def selection(self, chat_id, user_id, data):
        if data.startswith(("save:", "no:", "loc:", "place:")):
            allowed = settings.TELEGRAM_SAVE_USER_IDS
            if allowed and user_id not in allowed:
                return
            parts = data.split(":")
            key = parts[1] if len(parts) >= 2 else ""
            owner = f"{chat_id}:{user_id}"
            if not pending_save("tg", owner, key):
                self.send(chat_id, "Pedido expirado / Request expired. Send the photo again.")
                return
            if parts[0] == "no" and len(parts) == 2:
                cancel_save("tg", owner, key)
                self.send(chat_id, "Não guardado / Not saved.")
            elif parts[0] == "save" and len(parts) == 2:
                self.save_locations(chat_id, user_id, key, 0)
            elif parts[0] == "loc" and len(parts) == 3 and parts[2].isdigit():
                self.save_locations(chat_id, user_id, key, int(parts[2][:6]))
            elif parts[0] == "place" and len(parts) == 3:
                result = save_photo_reagent("tg", owner, key, parts[2])
                if result:
                    reagent, created = result
                    self.send(chat_id, "Guardado / Saved (pending review):" if created else
                              "Já existe no inventário / Already in inventory:")
                    self.locations(chat_id, reagent)
                else:
                    self.send(chat_id, "Local inválido ou pedido expirado / Invalid location or expired request.")
            else:
                self.send(chat_id, "Seleção inválida / Invalid selection.")
        elif data.startswith("r:"):
            try:
                reagent_id = UUID(data[2:])
            except ValueError:
                self.send(chat_id, "Seleção inválida / Invalid selection.")
                return
            reagent = search_reagents("", available_only=True).filter(pk=reagent_id).first()
            if reagent:
                self.locations(chat_id, reagent)
            else:
                self.send(chat_id, "Reagente indisponível / Reagent no longer available.")
        elif data.startswith("p:"):
            parts = data.split(":")
            query = cache.get(f"tg:{chat_id}:{user_id}:{parts[1]}") if len(parts) == 3 else None
            if not query or not parts[2].isdigit() or len(parts[2]) > 6:
                self.send(
                    chat_id, "Pesquisa expirada. Envie novamente. / Search expired. Search again."
                )
                return
            self.results(chat_id, query, parts[1], int(parts[2]))

    def locations(self, chat_id, reagent):
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
        # Split long records without truncating locations or relying on Markdown escaping.
        text = "\n".join(lines)
        while text:
            part, text = text[:1900], text[1900:]
            self.send(chat_id, part)
