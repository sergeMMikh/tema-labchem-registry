"""Telegram transport and read-only conversations backed by the Django inventory."""

import json
import urllib.error
import urllib.request
from uuid import UUID

from django.conf import settings
from django.core import signing
from django.core.cache import cache

from .search import search_reagents

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
        text = message.get("text", "").strip()
        command = text.split(" ", 1)[0].split("@", 1)[0].lower()
        if command in ("/start", "/help") or not text:
            self.send(
                chat_id,
                "TEMA Reagents\nEnvie o nome, CAS, fórmula ou fabricante.\n"
                "Send a reagent name, CAS, formula or manufacturer.\nEx.: acetone / 67-64-1",
            )
            return
        if command in ("/search", "/pesquisar"):
            text = text.partition(" ")[2].strip()
        if len(text) < 2 or len(text) > 200 or text.startswith("/"):
            self.send(chat_id, "Pesquisa: 2–200 caracteres / Search: 2–200 characters.")
            return
        # The short key fits Telegram's 64-byte callback limit; scope it to the user/chat.
        key = signing.Signer(salt="telegram-search").signature(f"{chat_id}:{user['id']}:{text}")[
            :16
        ]
        cache.set(f"tg:{chat_id}:{user['id']}:{key}", text, timeout=3600)
        self.results(chat_id, text, key, 0)

    def results(self, chat_id, query, key, page):
        results = search_reagents(query, available_only=True)
        count = results.count()
        if not count:
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
        if data.startswith("r:"):
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
