"""Text registration shared by Telegram and WhatsApp."""

import re
from secrets import token_hex

from django import forms
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.db import DatabaseError, transaction

from .bot_save import PAGE_SIZE, PENDING_SECONDS, storage_locations
from .forms import PackageForm, ReagentForm
from .models import Category, Location, Package, Reagent, StockMovement, Supplier
from .photo_lookup import inventory_match
from .search import normalize_name

LANGUAGES = ("en", "pt", "ru")
ADD_WORDS = (
    ("add", "add reagent", "add a reagent", "please add", "add it", "register"),
    ("adicionar", "adiciona", "adicione", "adicionar reagente", "registar", "adicionar por favor"),
    ("добавь", "добавить", "добавьте", "добавь реагент", "добавить реагент", "добавь пожалуйста"),
)
COMMANDS = {
    "confirm": ("confirm", "save", "confirmar", "guardar", "подтвердить", "сохранить"),
    "cancel": ("cancel", "cancelar", "отмена", "отменить"),
    "edit": ("edit", "change", "alterar", "editar", "изменить", "исправить"),
    "skip": ("skip", "saltar", "ignorar", "пропустить", "-"),
    "next": ("next", "seguinte", "далее"),
    "back": ("back", "anterior", "назад"),
}
MESSAGES = {
    "search_first": ("Search for the reagent first.", "Pesquise o reagente primeiro.", "Сначала найдите реагент через поиск."),
    "restricted": ("Saving is restricted.", "O registo está restrito.", "Добавление для этого пользователя недоступно."),
    "enter": ("Enter {field}.", "Indique {field}.", "Введите значение поля «{field}»."),
    "optional": ("Type Skip to leave it blank.", "Escreva Saltar para deixar em branco.", "Чтобы оставить поле пустым, напишите «Пропустить»."),
    "invalid": ("Invalid value. Check the format and try again.", "Valor inválido. Verifique o formato e tente novamente.", "Неверное значение. Проверьте формат и попробуйте снова."),
    "invalid_choice": ("Choose a number from the list.", "Escolha um número da lista.", "Выберите номер из списка."),
    "location": ("Choose a storage location by number.", "Escolha o número do local de armazenamento.", "Выберите номер места хранения."),
    "location_page": ("Page {page}/{pages}. Type Back or Next to browse.", "Página {page}/{pages}. Escreva Anterior ou Seguinte.", "Страница {page}/{pages}. Напишите «Назад» или «Далее»."),
    "no_locations": ("No storage locations are available. You can cancel this draft.", "Não há locais disponíveis. Pode cancelar este rascunho.", "Нет доступных мест хранения. Можно отменить черновик."),
    "review": ("Reagent card", "Ficha do reagente", "Карточка реагента"),
    "review_actions": ("1 Confirm · 2 Cancel · 3 Edit", "1 Confirmar · 2 Cancelar · 3 Alterar", "1 Подтвердить · 2 Отменить · 3 Изменить"),
    "edit": ("Which field do you want to change? Reply with its number.", "Que campo pretende alterar? Responda com o número.", "Какой пункт изменить? Ответьте его номером."),
    "cancelled": ("Draft cancelled.", "Rascunho cancelado.", "Черновик отменён."),
    "pending": ("Package status: Pending review", "Estado da embalagem: Pendente de revisão", "Статус упаковки: требует проверки"),
    "saved": ("Saved {name} at {location}.", "Registado {name} em {location}.", "Реагент «{name}» сохранён. Место хранения: {location}."),
    "duplicate": ("Already in inventory: {name}.", "Já existe no inventário: {name}.", "Уже есть в базе: {name}."),
    "retry": ("Could not save. The draft is still open. Please try again.", "Não foi possível guardar. O rascunho continua aberto. Tente novamente.", "Сохранить не удалось. Черновик открыт. Попробуйте ещё раз."),
    "quantity": ("Remaining quantity cannot exceed the initial quantity.", "A quantidade restante não pode exceder a inicial.", "Остаток не может превышать исходное количество."),
    "location_changed": ("That location is no longer available. Edit the location and confirm again.", "O local já não está disponível. Altere o local e confirme novamente.", "Место больше недоступно. Измените локацию и подтвердите снова."),
    "barcode": ("This barcode is already in use. Edit it and confirm again.", "O código de barras já está em uso. Altere-o e confirme novamente.", "Штрихкод уже используется. Измените его и подтвердите снова."),
}

# These fields are presented in order. Workflow status and audit fields are set on save.
FIELDS = {
    "name": ("Name", "Nome", "Название"),
    "formula": ("Formula", "Fórmula", "Формула"),
    "cas_number": ("CAS number", "Número CAS", "Номер CAS"),
    "supplier": ("Supplier / manufacturer", "Fornecedor / fabricante", "Поставщик / производитель"),
    "catalog_number": ("Catalogue number", "Referência de catálogo", "Каталожный номер"),
    "category": ("Category", "Categoria", "Категория"),
    "physical_state": ("Physical state", "Estado físico", "Физическое состояние"),
    "default_unit": ("Default unit", "Unidade predefinida", "Единица по умолчанию"),
    "sds_url": ("Safety data sheet URL", "URL da ficha de segurança", "Ссылка на паспорт безопасности"),
    "description": ("Description", "Descrição", "Описание"),
    "barcode": ("Barcode", "Código de barras", "Штрихкод"),
    "lot_number": ("Lot number", "Número de lote", "Номер партии"),
    "initial_quantity": ("Initial quantity", "Quantidade inicial", "Исходное количество"),
    "current_quantity": ("Remaining quantity", "Quantidade restante", "Остаток"),
    "unit": ("Package unit", "Unidade da embalagem", "Единица упаковки"),
    "concentration": ("Concentration", "Concentração", "Концентрация"),
    "received_at": ("Date received", "Data de receção", "Дата получения"),
    "opened_at": ("Date opened", "Data de abertura", "Дата вскрытия"),
    "expires_at": ("Expiry date", "Data de validade", "Срок годности"),
    "location": ("Storage location", "Local de armazenamento", "Место хранения"),
    "notes": ("Package notes", "Notas da embalagem", "Примечания к упаковке"),
}
FIELD_KEYS = list(FIELDS)
REQUIRED = {"name", "location"}
DATE_FIELDS = {"received_at", "opened_at", "expires_at"}
PHYSICAL_STATES = {
    "solid": ("Solid", "Sólido", "Твёрдое"),
    "liquid": ("Liquid", "Líquido", "Жидкое"),
    "gas": ("Gas", "Gás", "Газ"),
    "mixture": ("Mixture", "Mistura", "Смесь"),
    "other": ("Other", "Outro", "Другое"),
    "unknown": ("Unknown", "Desconhecido", "Неизвестно"),
}
STATE_KEYS = list(PHYSICAL_STATES)
FIELD_HINTS = {
    "cas_number": "67-64-1",
    "sds_url": "https://…",
    "initial_quantity": "12.5",
    "current_quantity": "12.5",
    **dict.fromkeys(DATE_FIELDS, "DD/MM/YYYY"),
}
NOT_FOUND = "Não encontrado na base de dados / Not found in the database / Реагент не найден в базе."


def command_key(text):
    return normalize_name(" ".join(re.sub(r"[/!?.,]+", " ", text).split()))


def matches_command(text, words):
    return command_key(text) in {command_key(word) for word in words}


def note_miss(channel, owner, *, photo=None):
    cache.set(f"bot-miss:{channel}:{owner}", {"photo": photo}, PENDING_SECONDS)


def clear_miss(channel, owner):
    cache.delete(f"bot-miss:{channel}:{owner}")


def numbered_option(text, options):
    if re.fullmatch(r"[0-9]{1,3}", text):
        index = int(text) - 1
        if 0 <= index < len(options):
            return options[index]
    return None


class BotRegistration:
    def __init__(self, channel, owner, send, *, can_save, offer_photo):
        self.channel = channel
        self.owner = owner
        self.send = send
        self.can_save = can_save
        self.offer_photo = offer_photo
        self.key = f"bot-registration:{channel}:{owner}"
        self.draft = cache.get(self.key)

    def handle(self, text):
        """Return true when the text belongs to the registration conversation."""
        if not self.draft:
            for language, words in zip(LANGUAGES, ADD_WORDS, strict=True):
                if matches_command(text, words):
                    self.begin(language)
                    return True
            return False
        if not self.can_save:
            self.say("restricted")
            return True
        if matches_command(text, COMMANDS["cancel"]):
            self.cancel()
        elif self.draft["step"] == "review":
            self.review_action(text)
        elif self.draft["step"] == "choose_field":
            self.choose_field(text)
        else:
            self.accept_field(text)
        return True

    def begin(self, language):
        self.draft = {"language": language, "step": "fill", "index": 0,
                      "values": {}, "id": token_hex(16)}
        miss = cache.get(f"bot-miss:{self.channel}:{self.owner}")
        if not self.can_save:
            self.say("restricted")
        elif miss is None:
            self.say("search_first")
        elif miss["photo"]:
            self.offer_photo(*miss["photo"])
        else:
            self.prompt_field()

    def translate(self, labels):
        return labels[LANGUAGES.index(self.draft["language"])]

    def message(self, key, **values):
        return self.translate(MESSAGES[key]).format(**values)

    def say(self, key, **values):
        self.send(self.message(key, **values))

    def send_lines(self, lines):
        message = ""
        for line in lines:
            if len(message) + len(line) >= 1900:
                self.send(message)
                message = ""
            message = f"{message}\n{line}" if message else line
        if message:
            self.send(message)

    def store(self):
        cache.set(self.key, self.draft, PENDING_SECONDS)

    @property
    def field(self):
        return FIELD_KEYS[self.draft["index"]]

    def prompt_field(self):
        field = self.field
        if field == "location":
            self.show_locations(0)
            return
        self.store()
        lines = [self.message("enter", field=self.translate(FIELDS[field]))]
        if field in FIELD_HINTS:
            lines.append(FIELD_HINTS[field])
        if field == "physical_state":
            lines.extend(f"{index}. {self.translate(PHYSICAL_STATES[value])}"
                         for index, value in enumerate(STATE_KEYS, 1))
        if field not in REQUIRED:
            lines.append(self.message("optional"))
        self.send("\n".join(lines))

    def show_locations(self, page):
        locations = storage_locations()
        pages = max(1, (len(locations) + PAGE_SIZE - 1) // PAGE_SIZE)
        page = min(max(0, page), pages - 1)
        options = locations[page * PAGE_SIZE:(page + 1) * PAGE_SIZE]
        self.draft.update(location_page=page, location_options=[str(item.pk) for item in options])
        self.store()
        if not options:
            self.say("no_locations")
            return
        lines = [self.message("location")]
        lines.extend(f"{index}. {item.full_path}" for index, item in enumerate(options, 1))
        if pages > 1:
            lines.append(self.message("location_page", page=page + 1, pages=pages))
        self.send_lines(lines)

    def accept_field(self, text):
        if self.field == "location":
            for command, offset in (("back", -1), ("next", 1)):
                if matches_command(text, COMMANDS[command]):
                    self.show_locations(self.draft["location_page"] + offset)
                    return
        try:
            value = self.clean_field(text)
        except ValidationError:
            self.say("invalid")
            return
        self.draft["values"][self.field] = value
        if self.draft["step"] == "edit" or self.draft["index"] == len(FIELD_KEYS) - 1:
            self.show_review()
        else:
            self.draft["index"] += 1
            self.prompt_field()

    def clean_field(self, text):
        field = self.field
        if matches_command(text, COMMANDS["skip"]):
            if field in REQUIRED:
                raise ValidationError("Required field")
            return "unknown" if field == "physical_state" else None
        if field == "location":
            value = numbered_option(text, self.draft["location_options"])
        elif field == "physical_state":
            value = numbered_option(text, STATE_KEYS)
            if value is None:
                value = next((key for key, labels in PHYSICAL_STATES.items()
                              if matches_command(text, (key, *labels))), None)
        else:
            return self.clean_input(field, text)
        if value is None:
            raise ValidationError("Unrecognized selection")
        return value

    @staticmethod
    def clean_input(field, text):
        if field in DATE_FIELDS:
            return forms.DateField(input_formats=["%d/%m/%Y"]).clean(text)
        if field in ("supplier", "category", "barcode"):
            model, key = {"supplier": (Supplier, "name"), "category": (Category, "name"),
                          "barcode": (Package, "barcode")}[field]
            return model._meta.get_field(key).formfield().clean(text)
        field_form = ReagentForm.base_fields.get(field) or PackageForm.base_fields[field]
        if field in ("initial_quantity", "current_quantity"):
            text = text.replace(",", ".")
        value = field_form.clean(text)
        if field == "cas_number":
            Reagent._meta.get_field(field).run_validators(value)
        if field in ("description", "notes") and len(value) > 500:
            raise ValidationError("Text exceeds 500 characters")
        return value

    def show_review(self):
        self.draft["step"] = "review"
        self.store()
        values = self.draft["values"]
        location = Location.objects.filter(pk=values["location"]).first()
        location_path = location.full_path if location else "—"
        lines = [self.message("review")]
        for field, labels in FIELDS.items():
            value = values.get(field)
            if field == "location":
                value = location_path
            elif field == "physical_state":
                value = self.translate(PHYSICAL_STATES[value or "unknown"])
            elif field in DATE_FIELDS and value:
                value = value.strftime("%d/%m/%Y")
            lines.append(f"{self.translate(labels)}: {'—' if value is None else value}")
        lines.extend((self.message("pending"), self.message("review_actions")))
        self.send_lines(lines)

    def review_action(self, text):
        action = numbered_option(text, ("confirm", "cancel", "edit"))
        if action == "confirm" or matches_command(text, COMMANDS["confirm"]):
            self.confirm()
        elif action == "cancel":
            self.cancel()
        elif action == "edit" or matches_command(text, COMMANDS["edit"]):
            self.draft["step"] = "choose_field"
            self.store()
            lines = [self.message("edit")]
            lines.extend(f"{index}. {self.translate(labels)}"
                         for index, labels in enumerate(FIELDS.values(), 1))
            self.send("\n".join(lines))
        else:
            self.say("review_actions")

    def choose_field(self, text):
        field = numbered_option(text, FIELD_KEYS)
        if field is None:
            field = next((key for key, labels in FIELDS.items()
                          if matches_command(text, (key, *labels))), None)
        if field is None:
            self.say("invalid_choice")
            return
        self.draft.update(step="edit", index=FIELD_KEYS.index(field))
        self.prompt_field()

    def cancel(self):
        cache.delete(self.key)
        clear_miss(self.channel, self.owner)
        self.say("cancelled")

    def confirm(self):
        values = self.draft["values"]
        initial = values.get("initial_quantity")
        remaining = values.get("current_quantity")
        if initial is not None and remaining is not None and remaining > initial:
            self.say("quantity")
            self.say("review_actions")
            return
        try:
            result, details = save_registration(values, self.channel, self.draft["id"])
        except DatabaseError:
            self.say("retry")
            return
        if result in ("saved", "duplicate"):
            cache.delete(self.key)
            clear_miss(self.channel, self.owner)
        self.say(result, **details)


@transaction.atomic
def save_registration(values, channel, draft_id):
    source_key = f"bot-text:{draft_id}"
    saved = Package.objects.select_related("location", "reagent").filter(source_key=source_key).first()
    if saved:
        return "saved", {"name": saved.reagent.name, "location": saved.location.full_path}
    location = Location.objects.filter(pk=values["location"], is_active=True).first()
    if location is None or location.children.filter(is_active=True).exists():
        return "location_changed", {}
    identity = {"name": values["name"], "cas": values.get("cas_number") or "",
                "catalog_number": values.get("catalog_number") or ""}
    existing = inventory_match(identity) or Reagent.objects.filter(name__iexact=values["name"]).first()
    if existing:
        return "duplicate", {"name": existing.name}
    barcode = values.get("barcode")
    if barcode and Package.objects.filter(barcode=barcode).exists():
        return "barcode", {}
    reagent = Reagent.objects.create(
        **{key: values[key] for key in ReagentForm.base_fields
           if key not in ("supplier", "category") and values.get(key) is not None},
        supplier=named_entry(Supplier, values.get("supplier")),
        category=named_entry(Category, values.get("category")),
    )
    package = Package.objects.create(
        **{key: values[key] for key in (*PackageForm.base_fields, *DATE_FIELDS)
           if key != "location" and values.get(key) is not None},
        barcode=barcode, location=location, reagent=reagent, source_key=source_key,
        status=Package.Status.PENDING,
    )
    StockMovement.objects.create(
        package=package, movement_type=StockMovement.Type.ADD,
        quantity_delta=package.current_quantity, quantity_after=package.current_quantity,
        to_location=location, reason=f"Text registration confirmed in {channel}",
    )
    return "saved", {"name": reagent.name, "location": location.full_path}


def named_entry(model, name):
    if name:
        existing = model.objects.filter(name__iexact=name).first()
        if existing:
            return existing
        return model.objects.get_or_create(name=name)[0]
    return None
