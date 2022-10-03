import logging
import sys
import re
from sqlalchemy.exc import PendingRollbackError

from aiogram import Dispatcher, types
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.utils.markdown import text, bold, italic, code
from aiogram.utils.emoji import emojize
from aiogram.types import ParseMode, ChatActions
from config.config import ADMIN_ID_TG, HOST, PORT

from .. import db_worker


########################################################################################################################
logger = logging.getLogger(__name__)
logging.basicConfig(
        level=logging.INFO,
        stream=sys.stdout,
        format='[%(asctime)s]:[%(levelname)s]:[%(filename)s]:[%(lineno)d]: %(message)s',
    )


########################################################################################################################
class ApiKeyRequest(StatesGroup):
    """
    Stateful class for creating logic for generating api keys and validating user data to the administrator
    """
    waiting_for_purpose = State()
    waiting_for_phone = State()


########################################################################################################################
async def api_cmd(message: types.Message, state: FSMContext):
    """
    0 action
        instruction
    """
    username = message.from_user.username
    logger.info(fr'[{username}]: Start /api command')
    await state.reset_state(with_data=False)

    db_worker.pending_rollback(username=message.from_user.username)

    try:
        sql_user = db_worker.get_user(tg_id=message.from_user.id)
        is_api = db_worker.is_api_keys(
            user=sql_user
        )
    except Exception as e:
        logger.error(f'[{username}]: Houston, we have got a problem {e}')
        answer = text(
            emojize(":man_mechanic:"), r"There was a big trouble when searching for you in the database\, "
                                       r"please try again and then write to the administrator\.")
        await message.answer(answer, parse_mode=ParseMode.MARKDOWN_V2)
        return

    if is_api:     # user is already has an api_keys
        answer = text(
            r'If you still do not have a private api key \- contact the administrator'
        )
        remove_keyboard = types.ReplyKeyboardRemove()
        await message.answer(answer, parse_mode=ParseMode.MARKDOWN_V2, reply_markup=remove_keyboard)
        answer = text(
            bold('Instructions for using api requests:'), '\n',
            '\n',
            bold('GET'),
            code(fr'http://{HOST}/api/words/<your_token>'), r'\- outputs all your words data', '\n',
            bold('GET'),
            code(fr'http://{HOST}/api/lesson/<your_token>'), r'\- forms and outputs the lesson', '\n',
            bold('GET'),
            code(fr'http://{HOST}/api/example/<your_token>/<example_id>'), r'\- displays example data by id', '\n',
            bold('GET'),
            code(fr'http://{HOST}/api/word/<your_token>/<word_id>'), r'\- displays word data by id', '\n',
            '\n',
            bold('POST'),
            code(fr'http://{HOST}/api/example/<your_token>/0'),
            code('{"example": "<your_example>"}'), r'\- writes the example to the database', '\n',
            bold('POST'),
            code(fr'http://{HOST}/api/word/<your_token>/0'),
            code('{"word": "<your_word>", "description": "<your_description>, "ex_id": "<your_example_id>"}'),
            r'\- writes the word to the database', '\n',
            '\n',
            bold('PUT'),
            code(fr'http://{HOST}/api/example/<your_token>/<example_id>'),
            code('{"example": "<your_example>"}'), r'\- updates the example data', '\n',
            bold('PUT'),
            code(fr'http://{HOST}/api/word/<your_token>/<word_id>'),
            code('{"word": "<your_word>", "description": "<your_description>}'), r'\- updates the word data', '\n',
            '\n',
            bold('DELETE'),
            code(fr'http://{HOST}/api/word/<your_token>/<word_id>'),
            r'\- removes the word and if the example is left empty it too', '\n',
            bold('DELETE'),
            code(fr'http://{HOST}/api/example/<your_token>/<example_id>'),
            r'\- removes the example and all its words', '\n',
        )
        await message.answer(answer, parse_mode=ParseMode.MARKDOWN_V2)
        logger.info(f'[{username}]: Finish /api command')
        await state.reset_state(with_data=False)
        return

    else:          # register new keys
        answer = text(
            emojize(r'There are only a couple of steps left to your private api key :key:')
        )
        remove_keyboard = types.ReplyKeyboardRemove()
        await message.answer(answer, parse_mode=ParseMode.MARKDOWN_V2, reply_markup=remove_keyboard)
        answer = text(
            emojize(r'Tell us what you would like to use the bot API for \(feel free to describe\)')
        )
        await message.answer(answer, parse_mode=ParseMode.MARKDOWN_V2)

    await state.update_data(
        purpose=None,
        phone=None,
    )

    logger.info(f'[{username}]: Jump to purpose input')
    await ApiKeyRequest.waiting_for_purpose.set()


async def ms_get_purpose_set_phone_input(message: types.Message, state: FSMContext):
    """
    1 action
        accept the response with the purpose
        set the wait to a phone number
    """
    username = message.from_user.username
    user_text = message.text

    logger.info(f'[{username}]: Catch user api`s purpose: "{user_text}"')

    if len(user_text) < 40:
        logger.info(f'[{username}]: Incorrect purpose - too small "{user_text}"')
        answer = text(
            emojize(':police_car: Be bold'), italic(
                f'"{message.text if len(message.text) <= 12 else message.text[:13] + "..."}"\n'),
            '\n',
            r'please describe what you would like to use the bot API for in more detail\.', '\n',
            '\n'
        )
        await message.answer(answer, parse_mode=ParseMode.MARKDOWN_V2)
        return

    answer = text(
        r"Great\, now enter your phone number where you will receive your private api key")
    await message.answer(answer, parse_mode=ParseMode.MARKDOWN_V2)

    await state.update_data(
        purpose=user_text,
    )

    logger.info(f'[{username}]: Jump to phone number input')
    await ApiKeyRequest.waiting_for_phone.set()


async def ms_get_phone_sql_admin_send(message: types.Message, state: FSMContext):
    """
    2 action
        accept the response with the phone number
        make sql func
        send admin req
    """
    username = message.from_user.username
    user_text = message.text.lower().strip()
    pattern = re.compile(r'\(?([0-9]{3})\)?([ .-]?)([0-9]{3})\2([0-9]{4})')

    logger.info(f'[{username}]: Catch user phone number: "{user_text}"')

    if not pattern.findall(user_text):
        logger.info(f'[{username}]: Incorrect phone number "{user_text}"')
        answer = text(
            emojize(r':police_car: Either our number filter is wrong\, or you have entered an invalid number '), italic(
                f'"{message.text if len(message.text) <= 12 else message.text[:13] + "..."}"\n'),
            '\n',
            r'Please try again', '\n',
            '\n'
        )
        await message.answer(answer, parse_mode=ParseMode.MARKDOWN_V2)
        return

    await message.bot.send_chat_action(message.from_user.id, ChatActions.TYPING)

    await state.update_data(
        phone=user_text,
    )

    data = await state.get_data()
    phone_number = data.get('phone')
    purpose = data.get('purpose')

    db_worker.pending_rollback(username=message.from_user.username)

    try:
        sql_user = db_worker.get_user(tg_id=message.from_user.id)
        db_worker.generate_api_keys(
            user=sql_user
        )
    except Exception as e:
        logger.error(f'[{username}]: Houston, we have got a problem {e}')
        answer = text(
            emojize(":man_mechanic:"), r"There was a big trouble when searching for you in the database\, "
                                       r"please try again and then write to the administrator\.")
        await message.answer(answer, parse_mode=ParseMode.MARKDOWN_V2)
        return

    try:
        answer = text(
            bold('API private key request'), '\n',
            r'Phone\:', code(f' {phone_number}'), '\n',
            r'Purpose\:', italic(f' {purpose}'), '\n',
            r'Key to send\:', code(f' {db_worker.get_user_api_key(user=sql_user)}'), '\n',
        )
        await message.bot.send_message(ADMIN_ID_TG, answer, parse_mode=ParseMode.MARKDOWN_V2)
    except PendingRollbackError as e:
        try:
            logger.error(f'[{username}]: Connection with db died {e}. Try to reconnect...')
            db_worker.session.rollback()
            answer = text(
                bold('API private key request'), '\n',
                r'Phone\:', code(f' {phone_number}'), '\n',
                r'Purpose\:', italic(f' {purpose}'), '\n',
                r'Key to send\:', code(f' {db_worker.get_user_api_key(user=sql_user)}'), '\n',
            )
            await message.bot.send_message(ADMIN_ID_TG, answer, parse_mode=ParseMode.MARKDOWN_V2)
        except Exception as e:
            logger.error(f'[{username}]: Houston, we have got a problem {e}')
            answer = text(
                emojize(":man_mechanic:"), r"There was a big trouble when searching for you in the database\, "
                                           r"please try again and then write to the administrator\.")
            await message.answer(answer, parse_mode=ParseMode.MARKDOWN_V2)
            return
    except Exception as e:
        logger.error(f'[{username}]: Houston, we have got a problem {e}')
        answer = text(
            emojize(":man_mechanic:"), r"There was a big trouble when searching for you in the database\, "
                                       r"please try again and then write to the administrator\.")
        await message.answer(answer, parse_mode=ParseMode.MARKDOWN_V2)
        return

    answer = text(
        r"Cool\, now all you have to do is wait for the admin to give you a private token")
    await message.answer(answer, parse_mode=ParseMode.MARKDOWN_V2)

    answer = text(
        bold('Instructions for using api requests:'), '\n',
        '\n',
        bold('GET'),
            code(fr'http://{HOST}:{PORT}/api/words/<your_token>'), r'\- outputs all your words data\.',
                r'Response example\:', code(
            '{"1":{"word": "Arrow", "description": "A weapon consisting of a thin, straight stick with a sharp '
            'point, designed to be shot from a bow.", "example_id": "1", "example": "We just imagine the arrows'
            ' because we fear them.", ...}'
            ), '\n',
        bold('GET'),
            code(fr'http://{HOST}:{PORT}/api/lesson/<your_token>'), r'\- forms and outputs the lesson',
                r'Response example\:', code(
            '[{"a": {"tg_id": 2, "word": "dizzy", "description": "make (someone) feel unsteady, confused, or amazed", '
            '"example": "Pops, what would you rather do? Spin around and get dizzy, or look at naked people", '
            '"category": "Adjective", "rating": 0, "word_id": 72, "is_main": false, "is_correct": false}, "b": '
            '{"tg_id": 2, "word": "canned", "description": "preserved or supplied in a sealed can.\ndrunk. (in can like'
            ' in botle)", "example": "Not a word to your mom about me getting canned\n\"canned beans\"", "category":'
            ' "Adjective", "rating": -3, "word_id": 45, "is_main": false, "is_correct": false}, "c": { "tg_id": 2, '
            '"word": "uncaring", "description": "not displaying sympathy or concern for others.", "example": "The '
            'universe is a cruel uncaring void\n\"people who are cruel to animals\"\n\"an uncaring father\"", '
            '"category": "Adjective", "rating": -3, "word_id": 38, "is_main": false, "is_correct": false}, "d": '
            '{ "tg_id": 2, "word": "sore", "description": "(of a part of body) painful or aching.\nsuffering pain from '
            'a part of body.\nupset and angry.", "example": "Are you a detective? Yes my gums are sore! Enough of '
            'this!", "category": "Adjective", "rating": -1, "word_id": 53, "is_main": true, "is_correct": true}, ...},'
            ), '\n',
        bold('GET'),
            code(fr'http://{HOST}:{PORT}/api/example/<your_token>/<example_id>'), r'\- displays example data by id',
                r'Response example\:', code(
            '{"ex_id": 14, "example": "Madame Web says we are each from different dimensions", "user_id": 2}'
            ), '\n',
        bold('GET'),
            code(fr'http://{HOST}:{PORT}/api/word/<your_token>/<word_id>'), r'\- displays word data by id',
                r'Response example\:', code(
            '{"word_id": 16, "word": "dimension", "description": "a measurable extent of a particular kind, such as '
            'length, breadth, depth, or height.", "example_id": 14}'
            ), '\n',
        '\n',
        bold('POST'),
            code(fr'http://{HOST}:{PORT}/api/example/<your_token>/0'), bold('->'),
                code('{"example": "<your_example>"}'), r'\- writes the example to the database',
                    r'Response example\:', code(
                '{"ex_id": 100, "example": "<your_example>", "user_id": 2}'
        ), '\n',
        bold('POST'),
            code(fr'http://{HOST}:{PORT}/api/word/<your_token>/0'), bold('->'),
                code('{"word": "<your_word>", "description": "<your_description>, "ex_id": "<your_example_id>"}'),
                    r'\- writes the word to the database',
                        r'Response example\:', code(
                '{"word_id": 1000, "word": "<your_word>", "description": "<your_description>, "example_id": 100}'
            ), '\n',
        '\n',
        bold('PUT'),
            code(fr'http://{HOST}:{PORT}/api/example/<your_token>/<example_id>'), bold('->'),
                code('{"example": "<your_example>"}'), r'\- updates the example data',
                    r'Response example\:', code(
                '{"ex_id": 100, "example": "<your_example>", "user_id": 2}'
        ), '\n',
        bold('PUT'),
            code(fr'http://{HOST}:{PORT}/api/word/<your_token>/<word_id>'), bold('->'),
                code('{"word": "<your_word>", "description": "<your_description>}'), r'\- updates the word data',
                    r'Response example\:', code(
                '{"word_id": 1000, "word": "<your_word>", "description": "<your_description>, "example_id": 100}'
        ), '\n',
        '\n',
        bold('DELETE'),
            code(fr'http://{HOST}:{PORT}/api/word/<your_token>/<word_id>'),
                r'\- removes the word and if the example is left empty it too',
                    r'Response example\:', code(
                '{"success": "Your data has been successfully deleted"}'
        ), '\n',
        bold('DELETE'),
            code(fr'http://{HOST}:{PORT}/api/example/<your_token>/<example_id>'),
                r'\- removes the example and all its words',
                    r'Response example\:', code(
                '{"success": "Your data has been successfully deleted"}'
        ), '\n',
        '\n')
    await message.answer(answer, parse_mode=ParseMode.MARKDOWN_V2)

    logger.info(f'[{username}]: Finish /api command')
    await state.reset_state(with_data=False)


########################################################################################################################
def register_api_handlers(dp: Dispatcher):
    """
    The function serves as a register of all the module coroutines in the correct sequence
     (used instead of decorators to create a more readable structure)
    """
    logger.info(f'[{dp}]: Register api handlers')

    dp.register_message_handler(api_cmd, commands=['api'], state='*')
    dp.register_message_handler(ms_get_purpose_set_phone_input, state=ApiKeyRequest.waiting_for_purpose)
    dp.register_message_handler(ms_get_phone_sql_admin_send, state=ApiKeyRequest.waiting_for_phone)
