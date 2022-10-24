import datetime
import logging
import sys

from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters import IDFilter
from aiogram import Dispatcher, types
from aiogram.utils.emoji import emojize
from aiogram.utils.markdown import text, bold, italic
from aiogram.types import ParseMode, ChatActions

from .. import db_worker


########################################################################################################################
logger = logging.getLogger(__name__)
logging.basicConfig(
        level=logging.INFO,
        stream=sys.stdout,
        format='[%(asctime)s]:[%(levelname)s]:[%(filename)s]:[%(lineno)d]: %(message)s',
    )


########################################################################################################################
async def start_cmd(message: types.Message, state: FSMContext):
    """
    independent action
        checks if the user exists in the database - creates a new user if necessary
        hello for user
    """
    logger.info(f'[{message.from_user.username}]: Use start command')

    db_worker.pending_rollback(username=message.from_user.username)

    if not db_worker.is_user(str(message.from_user.id)):
        logger.info(f'[{message.from_user.username}]: adding new user to "users" table...')
        await message.bot.send_chat_action(message.from_user.id, ChatActions.TYPING)
        sql_nickname = message.from_user.username
        if not sql_nickname:
            sql_nickname = f'user{message.from_user.id}'
            logger.warning(f'[{message.from_user.username}]: no username use {sql_nickname} instead')
        now = str(datetime.date.today())
        db_worker.add_user(tg_id=str(message.from_user.id),
                           nickname=sql_nickname,
                           lang_code=message.from_user.language_code,
                           shock_mode=0,
                           points=0,
                           is_blacklisted=False,
                           is_bot=bool(message.from_user.is_bot),
                           creation_time=now,
                           last_use_time=now,
                           current_use_time=now)
        logger.info(f'[{message.from_user.username}]: New user added to "users" table')

    await state.reset_state(with_data=False)
    txt = text(r"Let's start\!", " I'm waiting for you commands\n\nMore commands: /help")
    remove_keyboard = types.ReplyKeyboardRemove()
    await message.answer(txt, parse_mode=ParseMode.MARKDOWN_V2, reply_markup=remove_keyboard)


async def cancel_cmd(message: types.Message, state: FSMContext):
    """
    independent action
        cancel all actions
        reset state
    """
    logger.info(f'[{message.from_user.username}]: Use cancel command')
    await state.reset_state(with_data=False)
    txt = text(r'Action canceled\.', '\n',
               r'Menu with available commands\: /help')
    remove_keyboard = types.ReplyKeyboardRemove()
    await message.answer(txt, parse_mode=ParseMode.MARKDOWN_V2, reply_markup=remove_keyboard)


async def help_cmd(message: types.Message, state: FSMContext):
    """
    independent action
        reset state
        show all available bot command
    """
    logger.info(f'[{message.from_user.username}]: Use help command')
    await state.reset_state(with_data=False)
    txt = text(
        bold('Hi I\'m Teleword Bot'), emojize(' :robot_face:\n'),
        '\n',
        r'Here are the things that I can do\:', '\n',
        '\n',
        emojize(':gear: '), italic('Basic:'), '\n'
        r'\(commands from this list cancel any action\)', '\n',
        r'/start \-  let\'s start', '\n',
        r'/cancel /end /finish \- cancel any action', '\n'
        r'/help \- here you can find out what my features are', '\n'
        '\n',
        emojize(':blue_book: '), italic('Add your words:'), '\n'
        r'/add \- begin the process of adding a new word', '\n',
        '\n',
        emojize(':lower_left_paintbrush: '), italic('Conduct a lesson:'), '\n'
        r'\(shows  an error  if you have less than 15 words\)', '\n',
        r'/lesson \- start classic lesson', '\n',
        '\n',
        emojize(':bar_chart: '), italic('Show of statistics:'), '\n',
        r'/statistic \- view your stat', '\n',
        '\n',
        emojize(':mailbox: '), italic('Upload my words:'), '\n',
        r'/data \- send me files according to the given parameters', '\n',
        '\n',
        emojize(':butterfly: '), italic('Edit | Delete my data:'), '\n',
        r'/change \- calls the client to change your words', '\n',
        '\n',
        emojize(':fishing_pole_and_fish: '), italic('Get API-token and instruction:'), '\n',
        r'/api \- calls registration to get a unique api token', '\n',
        '\n',
        emojize(':gem: '), italic('View admin commands:'), '\n',
        emojize(r'\(does not work if you are not an admin :man_genie:\)'), '\n',
        r'/admin \- shows the admin panel', '\n',
        '\n',
        emojize(':watch: '), italic('Show bot time:'), '\n',
        r'/time /clock /now \- current time of the bot and time until the end of the day', '\n',
        sep=''
       )
    remove_keyboard = types.ReplyKeyboardRemove()
    await message.answer(txt, parse_mode=ParseMode.MARKDOWN_V2, reply_markup=remove_keyboard)


async def time_cmd(message: types.Message, state: FSMContext):
    """
    independent action
        reset state
        show  the user the internal time of the bot
             and how much time is left until the end of the day
    """
    logger.info(f'[{message.from_user.username}]: Use time command')
    current_time = datetime.datetime.today().strftime("%a, %H:%M")
    current_date = datetime.datetime.today().strftime('%d.%m.%Y')
    yesterday = datetime.date.today() + datetime.timedelta(days=1)
    yesterday = datetime.datetime(year=yesterday.year, month=yesterday.month, day=yesterday.day)
    time_left = yesterday - datetime.datetime.today()
    hours = str(time_left).split(':')[0]
    minutes = str(time_left).split(':')[1]
    await state.reset_state(with_data=False)
    txt = text(
        emojize(':stopwatch:'), r'Time\: ', bold(f'{current_time}'), '\n',
        '\n',
        emojize(':calendar:'), r'Date\: ', bold(f'{current_date}'), '\n',
        '\n',
        emojize(':hourglass:'), r'Until the end of the day lef\: ', bold(f'{hours} h {minutes} min'), '\n',
        '\n',
    )
    remove_keyboard = types.ReplyKeyboardRemove()
    await message.answer(txt, parse_mode=ParseMode.MARKDOWN_V2, reply_markup=remove_keyboard)


#####################################################################
async def admin_panel_cmd(message: types.Message, state: FSMContext):
    """
    independent action
        reset state
        show all available bot command for admin
    """
    logger.info(f'[{message.from_user.username}]: Show admin panel')
    await state.reset_state(with_data=False)

    txt = text(
                "/admin", italic(" >>> show admin panel"), '\n',
                "/admin_show_bl", italic(" >>> send current black list"), '\n',
                "/admintell", italic(" >>> sends to all users everything written after the command")
    )
    remove_keyboard = types.ReplyKeyboardRemove()
    await message.answer(txt, parse_mode=ParseMode.MARKDOWN_V2, reply_markup=remove_keyboard)


async def admin_show_bl_cmd(message: types.Message, state: FSMContext):
    """
    independent action
        reset state
        show black list of users to admin
    """
    logger.info(f'[{message.from_user.username}]: Show black list')
    await state.reset_state(with_data=False)

    db_worker.pending_rollback(username=message.from_user.username)

    black_list = db_worker.users_bl_list()
    if not black_list:
        txt = text(
            'Black list is empty'
        )
    else:
        txt = text(
            f'{black_list}'
        )
    await message.answer(txt, parse_mode=ParseMode.MARKDOWN_V2)


async def admin_tell_users_cmd(message: types.Message, state: FSMContext):
    """
    independent action
        Receives a command and a cue
        Separates the message
        Announces to all users
    """
    logger.info(f'[{message.from_user.username}]: Tell users...')
    await state.reset_state(with_data=False)
    db_worker.pending_rollback(username=message.from_user.username)

    speach = fr'{" ".join(message.text.split()[1:])}'
    if not speach:
        await message.answer(r'Message to users must be non-empty. Use /admintell <your message to all users>')
        return
    users = db_worker.get_users()
    logger.info(f'[{message.from_user.username}]: \nUsers count: "{len(users)}" \nSpeach to send "{speach}"')

    for user in users:
        try:
            await message.bot.send_message(
                chat_id=user.tg_id,
                text=speach,
            )
        except Exception as e:
            logger.error(f'[{user.nickname}]: Houston, we have got a problem {e}')
        finally:
            logger.error(f'[{user.nickname}]: Notified successfully')

    logger.info(f'[{message.from_user.username}]: Told users.')


########################################################################################################################
def register_handlers_common(dp: Dispatcher, admin_id: int):
    """
    The function serves as a register of all the module coroutines in the correct sequence
     (used instead of decorators to create a more readable structure)
    """
    logger.info(f'[{dp, admin_id}]: Register common handlers')
    dp.register_message_handler(start_cmd, commands=['start'], state='*')
    dp.register_message_handler(help_cmd, commands=['help'], state='*')
    dp.register_message_handler(cancel_cmd, commands=['cancel', 'end', 'finish'], state='*')
    dp.register_message_handler(time_cmd, commands=['time', 'now', 'clock'], state='*')
    dp.register_message_handler(admin_panel_cmd, IDFilter(user_id=admin_id), commands=['admin'], state='*')
    dp.register_message_handler(admin_show_bl_cmd, IDFilter(user_id=admin_id), commands=['admin_show_bl'], state='*')
    dp.register_message_handler(admin_tell_users_cmd, IDFilter(user_id=admin_id), commands=['admintell'], state='*')
