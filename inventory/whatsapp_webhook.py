import hashlib
import hmac
import json
import logging
import secrets
from concurrent.futures import ThreadPoolExecutor

from django.conf import settings
from django.core.cache import cache
from django.http import HttpResponse, HttpResponseBadRequest, HttpResponseForbidden
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from .whatsapp import WhatsAppBot, WhatsAppClient, WhatsAppError

logger = logging.getLogger(__name__)
audio_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="whatsapp-voice")


def _process_audio(message, cache_key):
    try:
        WhatsAppBot(WhatsAppClient()).handle(message)
    except Exception:
        cache.delete(cache_key)
        logger.exception("WhatsApp voice processing failed for %s", message.get("id"))


@csrf_exempt
@require_http_methods(["GET", "POST"])
def verify_webhook(request):
    if request.method == "POST":
        app_secret = settings.META_APP_SECRET
        signature = request.headers.get("X-Hub-Signature-256", "")
        if not app_secret or not signature.startswith("sha256="):
            return HttpResponseForbidden()
        expected = "sha256=" + hmac.new(
            app_secret.encode("utf-8"), request.body, hashlib.sha256
        ).hexdigest()
        if not hmac.compare_digest(signature, expected):
            return HttpResponseForbidden()
        try:
            event = json.loads(request.body)
        except (UnicodeDecodeError, json.JSONDecodeError):
            return HttpResponseBadRequest()
        if cache.get("whatsapp:auth-failed"):
            return HttpResponse(status=503)
        for entry in event.get("entry", []):
            for change in entry.get("changes", []):
                value = change.get("value", {})
                for message in value.get("messages", []):
                    logger.info(
                        "WhatsApp message received: id=%s from=%s type=%s",
                        message.get("id"), message.get("from"), message.get("type"),
                    )
                    message_id = message.get("id")
                    sender = message.get("from")
                    if not message_id or not sender:
                        continue
                    cache_key = f"whatsapp-message:{message_id}"
                    if not cache.add(cache_key, "processing", timeout=86400):
                        continue
                    try:
                        if message.get("type") == "audio":
                            audio_executor.submit(_process_audio, message, cache_key)
                        else:
                            WhatsAppBot(WhatsAppClient()).handle(message)
                    except WhatsAppError as error:
                        cache.delete(cache_key)
                        if error.code in (401, 403):
                            cache.set("whatsapp:auth-failed", True, timeout=60)
                        logger.error("WhatsApp API rejected message %s: HTTP %s", message_id, error.code)
                        return HttpResponse(status=503)
                    except Exception:
                        cache.delete(cache_key)
                        logger.exception("WhatsApp message handling failed for %s", message_id)
                        return HttpResponse(status=502)
                for status in value.get("statuses", []):
                    logger.info(
                        "WhatsApp message status: id=%s status=%s",
                        status.get("id"), status.get("status"),
                    )
        return HttpResponse(status=200)

    expected_token = settings.WHATSAPP_WEBHOOK_VERIFY_TOKEN
    supplied_token = request.GET.get("hub.verify_token", "")
    challenge = request.GET.get("hub.challenge")
    if (
        request.GET.get("hub.mode") == "subscribe"
        and expected_token
        and secrets.compare_digest(supplied_token, expected_token)
        and challenge is not None
    ):
        return HttpResponse(challenge, content_type="text/plain")
    return HttpResponseForbidden()
