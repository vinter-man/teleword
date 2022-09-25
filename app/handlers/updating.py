import logging
import sys

from aiogram import Dispatcher, types
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.utils.markdown import text, bold, italic
from aiogram.utils.emoji import emojize
from aiogram.types import ParseMode, ChatActions
from aiogram.dispatcher.filters import Text

from .. import db_worker


########################################################################################################################
logger = logging.getLogger(__name__)
logging.basicConfig(
        level=logging.INFO,
        stream=sys.stdout,
        format='[%(asctime)s]:[%(levelname)s]:[%(filename)s]:[%(lineno)d]: %(message)s',
    )


########################################################################################################################
class UpdateData(StatesGroup):

    waiting_for_data_type = State()
    waiting_for_action = State()
    waiting_for_data_id = State()
    waiting_for_new_data = State()
    waiting_for_deleting = State()
    waiting_for_next_step = State()


########################################################################################################################
async def change_cmd(message: types.Message, state: FSMContext):
    """
    0 action
        instruction
    """
    username = message.from_user.username
    logger.info(f'[{username}]: Start updating data')
    await state.reset_state(with_data=False)

    answer = text(
        bold('Small reminder:'), '\n',
        italic('(use /data first to select the desired word and example ids)'), '\n',
        bold('1.'), r'Choose what you want to change or delete', '\n',
        bold('2.'), r'Then choose an action \(delete \| change\)', '\n',
        bold('3.'), r'And then enter the new word\, description\, or example', '\n',
        '\n')
    remove_keyboard = types.ReplyKeyboardRemove()
    await message.answer(answer, parse_mode=ParseMode.MARKDOWN_V2, reply_markup=remove_keyboard)

    answer = text(
        emojize(r"Let\'s decide what we will change or delete :eyes:"))
    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    buttons = ['Word', 'Description', 'Example']
    keyboard.add(*buttons)
    await message.answer(answer, parse_mode=ParseMode.MARKDOWN_V2, reply_markup=keyboard)

    logger.info(f'[{username}]: Transfer user to the data to change choice')
    await UpdateData.waiting_for_data_type.set()


async def ms_get_data_type_set_action_choose(message: types.Message, state: FSMContext):
    """
    1 action
        accept the response with the user data type ('Word', 'Description', 'Example')
        set the wait to set the desired action ('Change', 'Delete')
    """
    username = message.from_user.username
    user_text = message.text.lower().strip()
    possible_answers = {'word', 'description', 'example'}

    logger.info(f'[{username}]: Catch data type: "{user_text}"')

    if user_text not in possible_answers:
        logger.info(f'[{username}]: Incorrect data type "{user_text}"')
        answer = text(
            emojize(':police_car: Something is wrong here'), italic(
                f'"{message.text if len(message.text) <= 12 else message.text[:13] + "..."}"\n'),
            '\n',
            italic('You can only work with your own words, descriptions and examples: '),
                                                            bold(f'{" | ".join(possible_answers)}\n'),
            '\n',
            r'Try it again\, just entering your answer below\.', '\n',
            '\n'
        )
        await message.answer(answer, parse_mode=ParseMode.MARKDOWN_V2)
        return

    await state.update_data(user_data_type=user_text)

    answer = text(
        fr"Okay, now choose what you want to do with your {user_text}")
    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    if user_text in 'word example'.split():
        buttons = ['Edit', 'Delete']
    else:           # description
        buttons = ['Edit']
    keyboard.add(*buttons)
    await message.answer(answer, parse_mode=ParseMode.MARKDOWN_V2, reply_markup=keyboard)

    logger.info(f'[{username}]: Jump to action input')
    await UpdateData.waiting_for_action.set()


async def ms_get_action_set_enter_data(message: types.Message, state: FSMContext):
    """
    2 action
        accept the response with the user action ('Edit', 'Delete')
        set the wait to data id ('word_id', 'example-id')
    """
    username = message.from_user.username
    user_text = message.text.lower().strip()
    possible_answers = {'edit', 'delete'}

    logger.info(f'[{username}]: Catch action: "{user_text}"')

    if user_text not in possible_answers:
        logger.info(f'[{username}]: Incorrect action "{user_text}"')
        answer = text(
            emojize(':police_car: Something is wrong here'), italic(
                f'"{message.text if len(message.text) <= 12 else message.text[:13] + "..."}"\n'),
            '\n',
            italic('You can only edit or delete your data: '),
                                                            bold(f'{" | ".join(possible_answers)}\n'),
            '\n',
            r'Try it again\, just entering your answer below\.', '\n',
            '\n'
        )
        await message.answer(answer, parse_mode=ParseMode.MARKDOWN_V2)
        return

    await state.update_data(user_data_action=user_text)
    data = await state.get_data()
    user_data_type = data.get("user_data_type")

    if user_data_type == 'example':
        answer = text(
            fr"Now all we need is the id of your example to {user_text} it")
    else:        # word description
        answer = text(
            fr"Now all we need is the id of your word to {user_text} it")

    keyboard = types.ReplyKeyboardRemove()
    await message.answer(answer, parse_mode=ParseMode.MARKDOWN_V2, reply_markup=keyboard)

    logger.info(f'[{username}]: Jump to id input')
    await UpdateData.waiting_for_data_id.set()


async def ms_get_id_set_action(message: types.Message, state: FSMContext):
    """
    3 action
        accept the response with the user data to change (id | data)
        set the action (delete from sql, new data to edit)
    """
    username = message.from_user.username
    user_text = message.text.lower().strip()
    data = await state.get_data()
    user_data_type = data.get("user_data_type")
    user_data_action = data.get("user_data_action")
    logger.info(f'[{username}]: Catch id | data: "{user_text}"')
    db_worker.pending_rollback(username=message.from_user.username)

    # example
    if user_data_type == 'example':
        example_obj = None
        try:
            await message.bot.send_chat_action(message.from_user.id, ChatActions.TYPING)
            user = db_worker.get_user(tg_id=message.from_user.id)
            if user_text.isdigit():
                example_obj = db_worker.get_user_example(user=user, example_id=int(user_text))
            if not example_obj:     # the specified numbers are not correct id or the user has entered text
                example_obj = db_worker.get_user_example(user=user, example=user_text)
        except Exception as e:
            logger.error(f'[{username}]: Houston, we have got a unknown sql problem {e}')
            answer = text(
                emojize(":oncoming_police_car:"), fr"There was a big trouble when searching your {user_data_type}\, "
                                                  r"please write to the administrator\.")
            await message.answer(answer, parse_mode=ParseMode.MARKDOWN_V2)
            return
        if not example_obj:
            logger.info(f'[{username}]: Incorrect id | data "{user_text}"')
            answer = text(
                emojize(":man_detective:"),
                  rf"We couldn\'t find the right {user_data_type}\, make sure you entered the correct example id", '\n',
                r'Try it again\, just entering your answer below\.', '\n',
                '\n')
            await message.answer(answer, parse_mode=ParseMode.MARKDOWN_V2)
            return

        await message.bot.send_chat_action(message.from_user.id, ChatActions.TYPING)
        example = example_obj.example
        words = [w.word for w in example_obj.words]
        await state.update_data(user_example_id=example_obj.ex_id)   # need for next step (deleting | editing)

        answer = text(
            bold(r"Here's what we found"), emojize(r':helicopter:'), '\n',
            '\n',
            bold(r" Example : "), italic(f'"{example}"'), '\n',
            bold(rf" With word{'s' if len(words) > 1 else ''} : "), italic(f'{", ".join(words)}'), '\n',
            '\n')
        await message.answer(answer, parse_mode=ParseMode.MARKDOWN_V2)

        if user_data_action == 'delete':
            answer = text(
                r"Are you sure you want to", bold("delete"), rf"an example", italic(f'"{example}"'),
                rf'\, this will result in the deletion of {"if all these words" if len(words) > 1 else "the world"}\:',
                italic(f'{", ".join(words)}'),
                emojize(r':firecracker:'), '\n',
                '\n',)
            inl_keyboard = types.InlineKeyboardMarkup()
            inl_buttons = [
                types.InlineKeyboardButton(text=text(emojize(':boom: Yes')), callback_data='call_delete_data'),
                types.InlineKeyboardButton(text=text(emojize(':dove_of_peace: No')), callback_data='call_cancel')]
            inl_keyboard.add(*inl_buttons)
            await message.answer(answer, parse_mode=ParseMode.MARKDOWN_V2, reply_markup=inl_keyboard)
            logger.info(f'[{username}]: Jump to deleting example')
            await UpdateData.waiting_for_deleting.set()
        else:    # edit
            answer = text(
                r"Enter what you want to ", bold("change"), rf"the example", italic(f'"{example}"'),
                    emojize(r'to :lower_left_crayon:'), '\n')
            await message.answer(answer, parse_mode=ParseMode.MARKDOWN_V2)
            logger.info(f'[{username}]: Jump to new {user_data_type} input')
            await UpdateData.waiting_for_new_data.set()

    # word | description
    else:
        word_obj = None
        try:
            flag = 'word_id'
            await message.bot.send_chat_action(message.from_user.id, ChatActions.TYPING)
            user = db_worker.get_user(tg_id=message.from_user.id)

            if user_text.isdigit():
                word_obj = db_worker.get_user_word(user=user, word_id=int(user_text))
            if not word_obj:     # the specified numbers are not correct id or the user has entered text
                if user_data_type == 'description':
                    flag = 'desc_text'
                    word_obj = db_worker.get_user_word(user=user, description=user_text)
                else:
                    flag = 'word_text'
                    word_obj = db_worker.get_user_word(user=user, word=user_text)
        except Exception as e:
            logger.error(f'[{username}]: Houston, we have got a unknown sql problem {e}')
            answer = text(
                emojize(":oncoming_police_car:"), fr"There was a big trouble when searching your {user_data_type}\, "
                                                  r"please write to the administrator\.")
            await message.answer(answer, parse_mode=ParseMode.MARKDOWN_V2)
            return
        if not word_obj:
            logger.info(f'[{username}]: Incorrect id | data "{user_text}"')
            answer = text(
                emojize(":man_detective:"),
                    rf"We couldn\'t find the right {user_data_type}\, make sure you entered the correct word id", '\n',
                r'Try it again\, just entering your answer below\.', '\n',
                '\n')
            await message.answer(answer, parse_mode=ParseMode.MARKDOWN_V2)
            return

        word = word_obj.word
        description = word_obj.description
        example_obj = db_worker.get_user_example(user=user, example_id=word_obj.example_id)
        example = example_obj.example
        await state.update_data(user_word_id=word_obj.word_id)     # need for next step (deleting | editing)

        answer = text(
            bold(r"Here's what we found"), italic(f'{"(first match with your input)" if flag != "word_id" else ""}'),
                emojize(r':helicopter:'), '\n',
            '\n',
            bold(r" Example : "), italic(f'"{example}"'), '\n',
            bold(r" Word : "), italic(f'{word}'), '\n',
            bold(r" Description : "), italic(f'"{description}"'), '\n',
            '\n')
        await message.answer(answer, parse_mode=ParseMode.MARKDOWN_V2)

        if user_data_action == 'delete':
            answer = text(
                r"Are you sure you want to", bold("delete"),
                    rf"the word {'with this description' if user_data_type == 'description' else ''}\? ",
                        emojize(r':firecracker:'), '\n',
                '\n',)
            inl_keyboard = types.InlineKeyboardMarkup()
            inl_buttons = [
                types.InlineKeyboardButton(text=text(emojize(':boom: Yes')), callback_data='call_delete_data'),
                types.InlineKeyboardButton(text=text(emojize(':dove_of_peace: No')), callback_data='call_cancel')]
            inl_keyboard.add(*inl_buttons)
            await message.answer(answer, parse_mode=ParseMode.MARKDOWN_V2, reply_markup=inl_keyboard)
            logger.info(f'[{username}]: Jump to deleting word')
            await UpdateData.waiting_for_deleting.set()
        else:    # edit
            answer = text(
                r"Enter what you want to ", bold("change"),
                    rf"the {'word' if user_data_type == 'word' else 'description'}",
                        italic(f'"{word if user_data_type == "word" else description}"'),
                            emojize(r'to :lower_left_crayon:'),
                '\n')
            await message.answer(answer, parse_mode=ParseMode.MARKDOWN_V2)
            logger.info(f'[{username}]: Jump to new {user_data_type} input')
            await UpdateData.waiting_for_new_data.set()


async def ms_get_new_data_set_finish(message: types.Message, state: FSMContext):
    """
    4 action
        accept the response with the new user data to change
        set the finish message with inline buttons
    """
    username = message.from_user.username
    user_text = message.text.lower().strip()
    user_text_length = len(user_text)
    data = await state.get_data()
    user_data_type = data.get("user_data_type")
    logger.info(f'[{username}]: New {user_data_type} data: "{user_text}"')
    db_worker.pending_rollback(username=message.from_user.username)

    if user_data_type == 'example':
        user_data_id = data.get("user_example_id")
    else:    # word | description
        user_data_id = data.get("user_word_id")

    if user_data_type == 'example' and (user_text_length > 400 or user_text_length < 5):
        answer = text(
            rf'The length of your example is {user_text_length}\. Try again')
        await message.answer(answer, parse_mode=ParseMode.MARKDOWN_V2)
        return
    if user_data_type == 'word' and (user_text_length > 135 or user_text_length < 1):
        answer = text(
            rf'The length of your word is {user_text_length}\. Try again')
        await message.answer(answer, parse_mode=ParseMode.MARKDOWN_V2)
        return
    elif user_data_type == 'description' and (user_text_length > 400 or user_text_length < 1):
        answer = text(
            rf'The length of your description is {user_text_length}\. Try again')
        await message.answer(answer, parse_mode=ParseMode.MARKDOWN_V2)
        return

    answer = text(
        rf'Please wait while we update your {user_data_type} \- this may take some time\.\.\.', '\n')
    await message.answer(answer, parse_mode=ParseMode.MARKDOWN_V2)

    await message.bot.send_chat_action(message.from_user.id, ChatActions.TYPING)

    try:
        db_worker.update_data(data_type=user_data_type, data_id=user_data_id, new_data=user_text)
        user = db_worker.get_user(tg_id=message.from_user.id)
        if user_data_type == 'example':
            example_obj = db_worker.get_user_example(
                user=user,
                example_id=user_data_id
            )
            words = [w.word for w in example_obj.words]
            answer = text(
                bold('Congratulate'), r'your data have been successfully updating to\:', '\n',
                bold('\n\tExample'), ' : ', italic(rf'"{example_obj.example}"'),
                bold(f"\n\tWord{'s' if len(words) > 1 else ''} : "), r' \: ', italic(fr'"{",".join(words)}"'))
        else:     # word | description
            word_obj = db_worker.get_user_word(
                user=user,
                word_id=user_data_id
            )
            example = db_worker.get_user_example(user=user, example_id=word_obj.example_id).example
            answer = text(
                bold('Congratulate'), r'your data have been successfully updating to\:', '\n',
                bold('\n\tExample'), ' : ', italic(rf'"{example}"'),
                bold('\n\tWord'), ' : ', italic(fr'{word_obj.word}'),
                bold('\n\tDescription'), ' : ', italic(fr'{word_obj.description}'))
    except Exception as e:
        logger.error(f'{username} Houston, we have got a unknown sql problem {e}')
        answer = text(
            emojize(":oncoming_police_car:"), r"There was a big trouble when edit your data\, "
                                              r"please write to the administrator\.")
        await message.answer(answer, parse_mode=ParseMode.MARKDOWN_V2)
        return

    inl_keyboard = types.InlineKeyboardMarkup()
    inl_buttons = [
        types.InlineKeyboardButton(text=text(emojize(':rowboat: Continue ')), callback_data='call_change'),
        types.InlineKeyboardButton(text=text(emojize(':desert_island: Exit ')), callback_data='call_cancel')]
    inl_keyboard.add(*inl_buttons)
    await message.answer(answer, parse_mode=ParseMode.MARKDOWN_V2, reply_markup=inl_keyboard)
    await UpdateData.waiting_for_next_step.set()


async def cb_get_delete_data_set_finish(call: types.CallbackQuery, state: FSMContext):
    """
    4 action
        accept the response with the data to delete
        set the finish message with inline buttons
    """
    username = call.from_user.username
    await call.message.delete_reply_markup()
    data = await state.get_data()
    user_data_type = data.get("user_data_type")
    if user_data_type == 'example':
        user_data_id = data.get("user_example_id")
    else:    # word | description
        user_data_id = data.get("user_word_id")
    logger.info(f'[{username}]: {user_data_type} to delete: "{user_data_id}"')
    db_worker.pending_rollback(username=message.from_user.username)

    answer = text(
        rf'Please wait while we delete your {user_data_type} \- this may take some time\.\.\.', '\n')
    await call.message.answer(answer, parse_mode=ParseMode.MARKDOWN_V2)

    await call.message.bot.send_chat_action(call.message.from_user.id, ChatActions.TYPING)

    try:
        db_worker.delete_data(data_type=user_data_type, data_id=user_data_id)
        user = db_worker.get_user(tg_id=call.message.chat.id)
        if user_data_type == 'example':
            example_obj = db_worker.get_user_example(
                user=user,
                example_id=user_data_id
            )
        else:
            example_obj = db_worker.get_user_example(
                user=user,
                example_id=user_data_id
            )
        if example_obj:
            raise FileExistsError(f'The file {example_obj} was not successfully deleted from the database')
        answer = text(
            bold('Congratulate'), r'your data have been successfully deleting\!', '\n',)
    except Exception as e:
        logger.error(f'{username} Houston, we have got a unknown sql problem {e}')
        answer = text(
            emojize(":oncoming_police_car:"), r"There was a big trouble when deleting your data\, "
                                              r"please write to the administrator\.")
        await call.message.answer(answer, parse_mode=ParseMode.MARKDOWN_V2)
        return

    inl_keyboard = types.InlineKeyboardMarkup()
    inl_buttons = [
        types.InlineKeyboardButton(text=text(emojize(':rowboat: Continue ')), callback_data='call_change'),
        types.InlineKeyboardButton(text=text(emojize(':desert_island: Exit ')), callback_data='call_cancel')]
    inl_keyboard.add(*inl_buttons)
    await call.message.answer(answer, parse_mode=ParseMode.MARKDOWN_V2, reply_markup=inl_keyboard)
    await UpdateData.waiting_for_next_step.set()


async def cb_delegate_change(call: types.CallbackQuery, state: FSMContext):
    """
    5 action
        delegate work in change_cmd coroutine
    """
    username = call.from_user.username
    logger.info(f'{username} Send call with /change command')

    await call.message.delete_reply_markup()
    await call.answer(show_alert=False)
    await change_cmd(message=call.message, state=state)


########################################################################################################################
def register_updating_handlers(dp: Dispatcher):
    logger.info(f'| {dp} | Register updating handlers')

    dp.register_message_handler(change_cmd, commands=['change'],
                                state='*')
    dp.register_message_handler(ms_get_data_type_set_action_choose,
                                state=UpdateData.waiting_for_data_type)
    dp.register_message_handler(ms_get_action_set_enter_data,
                                state=UpdateData.waiting_for_action)
    dp.register_message_handler(ms_get_id_set_action,
                                state=UpdateData.waiting_for_data_id)

    dp.register_message_handler(ms_get_new_data_set_finish,
                                state=UpdateData.waiting_for_new_data)
    dp.register_callback_query_handler(
        cb_get_delete_data_set_finish,
        Text(equals='call_delete_data'),
        state=UpdateData.waiting_for_deleting
    )

    dp.register_callback_query_handler(
        cb_delegate_change,
        Text(equals='call_change'),
        state=UpdateData.waiting_for_next_step
    )
