"""
SMALL TEST PART (simple)
1 testing for user
2 collecting information about today's date, errors, solutions on the first try
3 correct information writing ()

update the date during the test so that there is no such thing that it started at 23:59, finished tomorrow and it
incorrectly counted the system

if the user resets by start or cancel - the date must already be recorded

everything should, unlike writing new words, be written instantly and dynamically,

however, the set of words of ratings, etc. must be unchanged from the start of the test

first, the current list is compiled (completely ready) - then there are tests - and the system records everything
dynamically
"""
import asyncio
import logging
import sys
import time
import collections
import random

import requests
from aiogram import Bot, Dispatcher, types
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.utils.markdown import text, bold, italic, code, pre
from aiogram.utils.emoji import emojize
from aiogram.types import ParseMode, InputMediaPhoto, InputMediaVideo, ChatActions
from aiogram.dispatcher.filters import Text
from config.config import APP_KEY_OXF, APP_ID_OXF, URL_OXF

from .. import db_worker


########################################################################################################################
logger = logging.getLogger(__name__)
logging.basicConfig(
        level=logging.INFO,
        stream=sys.stdout,
        format='[%(asctime)s]:[%(levelname)s]:[%(filename)s]:[%(lineno)d]: %(message)s',
    )


########################################################################################################################
class ConductLesson(StatesGroup):

    waiting_for_answer = State()
    waiting_for_task = State()
    waiting_for_next_move = State()


########################################################################################################################
class MinLenError(TypeError):
    """
    It occurs when a lesson requests when the user does not have enough words
    """


def get_lesson_data(user: db_worker.Users) -> list:
    """
    independent action
        accepts a db_worker.Users instance (further "user")
        collects the user's words
        if there are less than 15 words - raises an exception
        makes a sequence of tests depending on the rating of the word
        Adds wrong answers depending on the speech type of the word
        Returns a list filled with 15-lists of 4 words
        of class namedtuple('WordItem', 'tg_id, word, description, example, category, rating, word_id')
        where 0 namedtuple is the correct answer
    """
    logger.info(f'{user.tg_id} Start get_lesson_data')
    WordItem = collections.namedtuple('WordItem', 'tg_id, word, description, example, category, rating, word_id')

    words = [
        WordItem(exx.user_tg_id, word.word, word.description, exx.example, word.category, word.rating, word.word_id)
        for exx in user.exxs for word in exx.words
    ]  # * itertools it
    words_len = len(words)
    if words_len < 15:
        raise MinLenError(f"{words_len}")
    words.sort(key=lambda word: word.rating)

    # the most difficult words are better learned 1/3(5):
    # 1 - 3 when repeated at the beginning (as a work on mistakes)
    # 14 - 15 and as the last tasks (like a boss in a video game,
    # so that the player has fun after passing)
    difficult_words = words[:5]
    random.shuffle(difficult_words)
    remaining_words = words[5:]
    random.shuffle(remaining_words)
    easy_words = remaining_words[:10]

    words_for_lesson = collections.deque(
        iterable=difficult_words[:3] + easy_words + difficult_words[3:],
        maxlen=15
    )

    data_for_lesson = []
    # data for the test 15 tests (1 correct and 3 wrong answers)
    for i in range(len(words_for_lesson)):
        random.shuffle(words)  # i mix each time, to improve accident
        test_words = []  # 4 words, in the first place is always correct

        right_word = words_for_lesson.popleft()
        test_words.append(right_word)

        for word in words:
            if len(test_words) == 4:  # 4 words
                break
            if word not in test_words and word.category == right_word.category:
                # the best learning effect is when the words are not just random,
                # but belong to the same part of speech ...
                wrong_word = word
                test_words.append(wrong_word)

        if len(test_words) != 4:  # ... but the user does not always have enough words ...
            for word in words:
                if len(test_words) == 4:
                    break
                if word not in test_words:
                    # ... therefore, fill in the missing ones in order,
                    # random.shuffle at the beginning will prevent repetitions
                    wrong_word = word
                    test_words.append(wrong_word)

        data_for_lesson.append(test_words)

    logger.info(f'{user.nickname} Return data for lesson')
    # [[namedtuple('WordItem', right), namedtuple('WordItem', wrong),
    #   namedtuple('WordItem', wrong), namedtuple('WordItem', wrong)], ...]
    return data_for_lesson


async def lesson_cmd(message: types.Message, state: FSMContext):
    """
    0 action
        instruction
    """
    username = message.from_user.username
    logger.info(f'{username} Start lesson')
    await state.reset_state(with_data=False)

    answer = text(
        emojize(r":person_in_lotus_position: Wait until we prepare a lesson for you \- it can take some time\."))
    await message.answer(answer, parse_mode=ParseMode.MARKDOWN_V2)

    await message.bot.send_chat_action(message.from_user.id, ChatActions.TYPING)  # comfortable waiting
    user_db = db_worker.get_user(tg_id=message.from_user.id)

    try:
        lesson_data = get_lesson_data(user_db)
    except MinLenError as e:
        logger.info(f'{username} Not enough words for lesson')
        answer = text(
                emojize(":cop: You need at least"), bold("15"), "words to start a lesson, you have only",
                bold(f"{e}."))
        await message.answer(answer, parse_mode=ParseMode.MARKDOWN_V2)
        return
    except Exception as e:
        logger.error(f'{username} Houston, we have got a problem {e, user_db}')
        answer = text(
                emojize(r":oncoming police car: There was a big trouble when compiling your test, "
                        r"please write to the administrator\."))
        await message.answer(answer, parse_mode=ParseMode.MARKDOWN_V2)
        return

    answer = text(
            bold("Let\'s start the lesson\n"),
            '\n',
            emojize(':face_with_monocle:'), 'Short information\n',
            '\tThe lesson consists of 15 tasks composed of your words according to a special', r'algorithm\.', '\n',
            '\tThe lesson is decided in one sitting', r'\- if you use another commander during testing \- all progress'
                                                      r' will erase\.', '\n',
            '\tThe task end when 15 correct answers are', r'given\.', '\n',
            '\n',
            emojize(':sunglasses:'), 'Tips\n',
            '\tFor convenience, use the buttons, instead of manual input of', r'letters\.', '\n',
            '\tTry to first find a solution, despite the answer options and only when you remember',
                                                      r'\- find the desired option\.', '\n',
            '\tThe number of attempts is not limited, but try to go through the task without errors maxently straining',
                                                      r'your memory\.',
            '\n')
    await message.answer(answer, parse_mode=ParseMode.MARKDOWN_V2)

    await state.update_data(
        lesson_data=lesson_data,
        task_number=0,
        first_try=0,
        mistake=0,
        total_try=0,
        current_task=None)

    logger.info(f'{username} Transfer user to the lesson')
    await ConductLesson.waiting_for_task.set()


async def ms_get_task_number_issues_task(message: types.Message, state: FSMContext):
    """
    1 action
        check the task number
        complete a lesson | form a current task
    """
    username = message.from_user.username
    data = await state.get_data()
    lesson_data = data['lesson_data']
    task_number = data['task_number']
    first_try = data['first_try']
    logger.info(f'{username} lesson {task_number}')

    # user reached the end and ended the lesson
    if task_number == 15:
        logger.info(f'{username} Finish lesson')
        await message.bot.send_chat_action(message.from_user.id, ChatActions.TYPING)

        # * sql changed the date of use, statistic

        await state.update_data(
            lesson_data=lesson_data,
            task_number=0,
            first_try=0,
            mistake=0,
            total_try=0,
            current_task=None)

        answer = text(
            bold('End of the lesson'), emojize(':tada:'), '\n',
            '\n',
            emojize(':zap:'), italic('Result'), bold(f'{int((first_try / 15) * 100)}%\n'))

        inl_keyboard = types.InlineKeyboardMarkup()
        inl_buttons = [
            types.InlineKeyboardButton(text=text(emojize(':person_climbing: Once again')), callback_data='call_lesson'),
            types.InlineKeyboardButton(text=text(emojize(':snow_capped_mountain: Exit')), callback_data='call_cancel')]
        inl_keyboard.add(*inl_buttons)

        await message.answer(answer, parse_mode=ParseMode.MARKDOWN_V2, reply_markup=inl_keyboard)
        await ConductLesson.waiting_for_next_move.set()
        return

    # It may be that the user has added the same word with different examples,
    # in this case there will be several correct answers.
    # This approach is quite good because the word will be remembered in several contexts
    current_lesson = lesson_data[task_number]
    main_correct_word = current_lesson[0]
    current_lesson_data = {'a': None, 'b': None, 'c': None, 'd': None}
    AnswerOption = collections.namedtuple('AnswerOption', 'word_obj, is_correct')

    current_words = []
    correct_pattern = main_correct_word[1].lower().strip()
    for word in current_lesson:
        word_pattern = word[1].lower().strip()
        if word_pattern == correct_pattern:
            current_words.append(AnswerOption(word, True))
        else:
            current_words.append(AnswerOption(word, False))

    random.shuffle(current_words)    # answer options mixed
    for n, k in enumerate(current_lesson_data.keys()):
        current_lesson_data[k] = current_words[n]

    answer = text(
            bold(f"{task_number + 1}"), r'Select the correct description of the word\.', '\n',
            '\n',
            r'Word\:', '\n',
            bold(f'"{main_correct_word[1]}"\n'),
            '\n',
            r'Answers\:', '\n',
            r' a\.', italic(f'{current_lesson_data.get("a").word_obj[2]}\n'),
            r' b\.', italic(f'{current_lesson_data.get("b").word_obj[2]}\n'),
            r' c\.', italic(f'{current_lesson_data.get("c").word_obj[2]}\n'),
            r' d\.', italic(f'{current_lesson_data.get("d").word_obj[2]}\n'),
            '\n')

    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2, one_time_keyboard=True)
    buttons = ['a', 'b', 'c', 'd']
    keyboard.add(*buttons)
    await message.answer(answer, parse_mode=ParseMode.MARKDOWN_V2, reply_markup=keyboard)

    await state.update_data(
        current_task=current_lesson_data)
    await ConductLesson.waiting_for_answer.set()


async def ms_get_answer_set_task(message: types.Message, state: FSMContext):
    """
    2 action
        text
    """
    username = message.from_user.username
    data = await state.get_data()
    task_number = data['task_number']
    logger.info(f'{username} lesson {task_number} catch answer')

    await message.answer(f'{message.text, data["current_task"]}')
    await state.update_data(
        task_number=task_number + 1)
    await ConductLesson.waiting_for_task.set()
    pass


########################################################################################################################
def register_lesson_handlers(dp: Dispatcher):
    logger.info(f'| {dp} | Register lesson handlers')

    dp.register_message_handler(lesson_cmd, commands=['lesson'], state='*')
    dp.register_message_handler(ms_get_task_number_issues_task, state=ConductLesson.waiting_for_task)
    dp.register_message_handler(ms_get_answer_set_task, state=ConductLesson.waiting_for_answer)
