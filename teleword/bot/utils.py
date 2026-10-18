from contextlib import suppress

from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery

# FSM data that survives between flows: /add offers to reuse the last example.
PERSISTENT_KEYS = ("last_example",)


async def reset_state(state: FSMContext) -> None:
    data = await state.get_data()
    await state.set_data({k: data[k] for k in PERSISTENT_KEYS if k in data})
    await state.set_state(None)


async def drop_markup(callback: CallbackQuery) -> None:
    """Removes the inline keyboard the user just pressed, so it cannot be pressed twice."""
    await callback.answer()
    if callback.message is not None:
        with suppress(TelegramBadRequest):
            await callback.message.edit_reply_markup(reply_markup=None)


def shorten(text: str, limit: int = 15) -> str:
    return text if len(text) <= limit else text[: limit - 1] + "…"
