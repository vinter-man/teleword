import logging
import os
import sys
import datetime
import matplotlib.pyplot as plt

from aiogram import Dispatcher, types
from aiogram.dispatcher import FSMContext
from aiogram.utils.markdown import text, bold
from aiogram.utils.emoji import emojize
from aiogram.types import ParseMode, ChatActions

from config.config import BACKUP_GRAPH

from .. import db_worker


########################################################################################################################
logger = logging.getLogger(__name__)
logging.basicConfig(
        level=logging.INFO,
        stream=sys.stdout,
        format='[%(asctime)s]:[%(levelname)s]:[%(filename)s]:[%(lineno)d]: %(message)s',
    )


########################################################################################################################
def build_graph(user_id, days, total, mistakes, first_try):
    logger.info(f'{user_id} Start build graph with: \n\n{days}\n{total}\n{mistakes}\n{first_try}\n')

    picture = plt.figure(
        figsize=(6.4, 4.8),
        dpi=100,
        facecolor='#1e262c',
        edgecolor='#1e262c'
    )
    graph = picture.add_subplot(1, 1, 1)

    graph.grid(
        visible=True,
        which='major',
        axis='both',
        alpha=0.1,
        antialiased=True,
        dash_capstyle='butt'
    )

    graph.set_facecolor('#1e262c')

    graph.tick_params(
        axis='both',
        color='#1e262c',
        labelcolor='#c4c9cd'
    )
    graph.spines['bottom'].set_color('#1e262c')
    graph.spines['top'].set_color('#1e262c')
    graph.spines['right'].set_color('#1e262c')
    graph.spines['left'].set_color('#1e262c')

    graph.fill_between(
        days, mistakes,
        color='#43c4e3',
        alpha=0.10
    )
    graph.fill_between(
        days, first_try,
        color='#43c4e3',
        alpha=0.15
    )
    graph.fill_between(
        days, total,
        color='#43c4e3',
        alpha=0.20
    )

    graph.plot(
        days, total,
        color='#43c4e3',
        solid_capstyle='round',
        linestyle='solid',
        marker='.',
        markerfacecolor='white',
        markersize=4,
        linewidth=1.5)

    logger.info(f"{user_id} here f'temporary/statistic_{user_id}_{str(datetime.date.today())}.png'")
    pic_name = f'temporary/statistic{user_id}.png'
    picture.savefig(pic_name)
    logger.info(f'{user_id} Graph successfully saved to {pic_name}')
    return pic_name


def get_seven_day():
    week = ['Mo', 'Tu', 'We', 'Th', 'Fr', 'Sr', 'Su']
    today = datetime.datetime.today().weekday()
    return week[-1:today:-1][::-1] + week[0:today] + [week[today]]


async def statistic_cmd(message: types.Message, state: FSMContext):

    username = message.from_user.username
    logger.info(f'{username} Start statistic')
    await state.reset_state(with_data=False)

    answer = text(
        emojize(r"Wait until we prepare your statistics \- it may take some time "
                                                    r":new_moon_with_face::chart_with_upwards_trend: "))
    remove_keyboard = types.ReplyKeyboardRemove()
    await message.answer(answer, parse_mode=ParseMode.MARKDOWN_V2, reply_markup=remove_keyboard)
    await message.bot.send_chat_action(message.from_user.id, ChatActions.TYPING)

    db_worker.pending_rollback(username=message.from_user.username)

    try:
        db_worker.change_user_last_using(
            user_tg_id=str(message.from_user.id),
            flag='check'
        )
    except Exception as e:
        logger.error(f'{username} unknown sql error {e}')

    try:
        user = db_worker.get_user(tg_id=message.from_user.id)
    except Exception as e:
        logger.error(f'{username} Houston, we have got a problem {e, message.from_user.id}')
        answer = text(
            emojize(":oncoming_police_car:"), r"There was a big trouble when compiling your test\, "
                                              r"please try again and then write to the administrator\.")
        await message.answer(answer, parse_mode=ParseMode.MARKDOWN_V2)
        return

    try:
        total_words_count = db_worker.word_count(user_tg_id=message.from_user.id)
    except Exception as e:
        logger.error(f'{username} Houston, we have got a problem {e, message.from_user.id}')
        total_words_count = 'error, please try again and then write to the admin'

    answer = text(
        emojize(':stopwatch: Shock mode\n'),
        bold(f'{user.shock_mode} days\n'),
        '\n',
        emojize(':airplane_arriving: First Use\n'),
        bold(f'{user.creation_time}\n'),
        '\n',
        emojize(':gem: Total points\n'),
        bold(f'{user.points} points\n'),
        '\n',
        emojize(':blue_book: Total words\n'),
        bold(f'{total_words_count} words\n'),
        '\n')

    try:
        last_seven_user_log_list = db_worker.get_user_stat(
            user_tg_id=message.from_user.id,
            limit=7
        )
        graph_data = db_worker.build_total_mistakes_firsttry_data_for_graph(
            user_sql_logs=last_seven_user_log_list
        )
    except Exception as e:
        logger.error(f'{username} Houston, we have got a unknown sql problem {e}')
        photo = BACKUP_GRAPH
    else:
        photo = build_graph(
            user_id=str(message.from_user.id),
            days=get_seven_day(),
            total=graph_data["total"],
            mistakes=graph_data["mistakes"],
            first_try=graph_data["first_try"]
        )
    try:
        await message.answer_photo(
            photo=open(photo, 'rb'),
            caption=answer,
            parse_mode=ParseMode.MARKDOWN_V2,
        )
    except Exception as e:
        logger.error(f'{username} Houston, we have got a problem {e, photo}')
        await message.answer(
            text=answer,
            parse_mode=ParseMode.MARKDOWN_V2,
        )
    finally:
        if photo != BACKUP_GRAPH:
            os.remove(photo)
            logger.info(f'{username} Graph {photo} successfully removed')
    logger.info(f'{username} Statistical data successfully sent to the user')


########################################################################################################################
def register_statistic_handlers(dp: Dispatcher):
    logger.info(f'| {dp} | Register statistic handlers')
    dp.register_message_handler(statistic_cmd, commands=['statistic'], state='*')
