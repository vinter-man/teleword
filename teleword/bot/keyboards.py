from aiogram.filters.callback_data import CallbackData
from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder


class Nav(CallbackData, prefix="nav"):
    """Simple navigation buttons: the action names a step of some flow."""

    action: str


class Answer(CallbackData, prefix="ans"):
    task: int
    key: str


class ExportChoice(CallbackData, prefix="exp"):
    """Carries the choices made so far, so the /data flow needs no FSM state."""

    selection: str = ""
    order: str = ""
    fmt: str = ""


class EditChoice(CallbackData, prefix="edit"):
    field: str = ""
    action: str = ""


class ApiDecision(CallbackData, prefix="apikey"):
    action: str
    user_id: int


def keyboard(*buttons: tuple[str, CallbackData], width: int = 2) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for text, data in buttons:
        builder.button(text=text, callback_data=data)
    builder.adjust(width)
    return builder.as_markup()


EXIT = ("🏝 Exit", Nav(action="cancel"))
