import asyncio
import copy
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


def get_lesson_data(tg_id: str) -> list:
    """
    independent action
        accepts a db_worker.Users instance (further "user")
        collects the user's words
        if there are less than 15 words - raises an exception
        makes a sequence of tests depending on the rating of the word
        Adds wrong answers depending on the speech type of the word
        Returns a list filled with 15-lists of 4 words
        of dict {'tg_id', 'word', 'description', 'example', 'category', 'rating', 'word_id', 'is_main'}
    """
    logger.info(f'{tg_id} Start get_lesson_data')
    words = db_worker.get_words_data(user_tg_id=tg_id)
    words_len = len(words)
    if words_len < 15:
        raise MinLenError(f"{words_len}")
    words.sort(key=lambda word: word['rating'], reverse=True)

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
            if word not in test_words and word["category"] == right_word["category"]:
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

    # [[{w}, {w}, {w}, {w}], ...]

    # It may be that the user has added the same word with different examples,
    # in this case there will be several correct answers.
    # This approach is quite good because the word will be remembered in several contexts
    ready_tasks = []
    for task in data_for_lesson:
        task = copy.deepcopy(task)     # Each test should not affect the state of all words in general
        main_correct_word = task[0]
        main_correct_word["is_main"] = True
        correct_pattern = main_correct_word["word"].lower().strip()
        for w in task:
            w_pattern = w["word"].lower().strip()
            if w_pattern == correct_pattern:
                w["is_correct"] = True
            else:
                w["is_correct"] = False

        current_lesson_data = {'a': None, 'b': None, 'c': None, 'd': None}
        random.shuffle(task)  # answer options mixed
        for n, k in enumerate(current_lesson_data.keys()):
            current_lesson_data[k] = task[n]

        ready_tasks.append(current_lesson_data)

    # [{aw, bw, cw, dw}, {}, {}, {}, ...]
    logger.info(f'{tg_id} Return data for lesson')
    return ready_tasks


async def lesson_cmd(message: types.Message, state: FSMContext):
    """
    0 action
        instruction
    """
    username = message.from_user.username
    logger.info(f'{username} Start lesson')
    await state.reset_state(with_data=False)

    answer = text(
        emojize(r":person_in_lotus_position: Wait until we prepare a lesson for you \- it can take some time\.\.\."))
    remove_keyboard = types.ReplyKeyboardRemove()
    await message.answer(answer, parse_mode=ParseMode.MARKDOWN_V2, reply_markup=remove_keyboard)

    await message.bot.send_chat_action(message.from_user.id, ChatActions.TYPING)  # comfortable waiting

    try:
        lesson_data = get_lesson_data(str(message.chat.id))
    except MinLenError as e:
        logger.info(f'{username} Not enough words for lesson')
        answer = text(
                emojize(":cop: You need at least"), bold("15"), "words to start a lesson, you have only",
                bold(f"{e}."))
        await message.answer(answer, parse_mode=ParseMode.MARKDOWN_V2)
        return
    except Exception as e:
        logger.error(f'{username} Houston, we have got a problem {e}')
        answer = text(
                emojize(":oncoming_police_car:"), r"There was a big trouble when compiling your test\, "
                                                                             r"please write to the administrator\.")
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

    inl_keyboard = types.InlineKeyboardMarkup()
    inl_buttons = [
        types.InlineKeyboardButton(text=text(emojize(':snowboarder: Start')), callback_data='call_get_task'),
        types.InlineKeyboardButton(text=text(emojize(':snow_capped_mountain: Exit')), callback_data='call_cancel')]
    inl_keyboard.add(*inl_buttons)

    await message.answer(answer, parse_mode=ParseMode.MARKDOWN_V2, reply_markup=inl_keyboard)

    await state.update_data(
        lesson_data=lesson_data,
        task_number=0,
        current_task=None,
        lesson_stats=[],
    )

    logger.info(f'{username} Transfer user to the lesson')
    await ConductLesson.waiting_for_task.set()


async def cb_get_task_number_issues_task(call: types.CallbackQuery, state: FSMContext):
    """
    1 action
        check the task number
        complete a lesson | form a current task
    """
    await call.message.delete_reply_markup()
    username = call.from_user.username
    data = await state.get_data()
    lesson_data = data['lesson_data']
    task_number = data['task_number']
    lesson_stats = data['lesson_stats']
    logger.info(f'{username} lesson {task_number}')

    ###########################################
    # user reached the end and ended the lesson
    if task_number == 15:
        logger.info(f'{username} Finish lesson')

        answer = text(
            bold('You have successfully coped!\n'),
            emojize(r':man_scientist: Give me a little time to calculate your result\.\.\.'), '\n')

        remove_keyboard = types.ReplyKeyboardRemove()

        await call.message.answer(answer, parse_mode=ParseMode.MARKDOWN_V2, reply_markup=remove_keyboard)
        await call.message.bot.send_chat_action(call.from_user.id, ChatActions.TYPING)

        first_try = 0
        mistakes = 0
        for word_stat_data in lesson_stats:
            # total first attempt
            if word_stat_data['attempts'] == 1:
                first_try += 1
            # total mistakes
            mistakes += word_stat_data['mistakes']
            # change sql word rating
            try:
                db_worker.change_rating(
                    word_id=word_stat_data['sql_id'],
                    new_rating=word_stat_data['current_rating']
                )
            except KeyError as e:
                logger.error(f'{username} sql error {e}')
            except Exception as e:
                logger.error(f'{username} unknown sql error {e}')

        await call.message.bot.send_chat_action(call.from_user.id, ChatActions.TYPING)
        success_percentage = int((first_try / 15) * 100)

        # shock mode
        try:
            db_worker.change_user_last_using(
                user_tg_id=str(call.message.chat.id),
                flag='change'
            )
        except Exception as e:
            logger.error(f'{username} unknown sql error {e}')

        # daily statistics
        try:
            db_worker.add_or_change_day_stat(
                tg_id=str(call.message.chat.id),
                first_try=first_try,
                mistakes=mistakes,
            )
        except Exception as e:
            logger.error(f'{username} unknown sql error {e}')

        await state.update_data(
            lesson_data=lesson_data,
            task_number=0,
            current_task=None,
            lesson_stats=[])

        answer = text(
            bold('End of the lesson'), emojize(':tada:'), '\n',
            '\n',
            emojize(':zap:'), italic('Result'), bold(f'{success_percentage}%\n'))

        inl_keyboard = types.InlineKeyboardMarkup()
        inl_buttons = [
            types.InlineKeyboardButton(text=text(emojize(':person_climbing: Once again')), callback_data='call_lesson'),
            types.InlineKeyboardButton(text=text(emojize(':mountain: Exit')), callback_data='call_cancel')]
        inl_keyboard.add(*inl_buttons)

        await call.message.answer(answer, parse_mode=ParseMode.MARKDOWN_V2, reply_markup=inl_keyboard)
        await ConductLesson.waiting_for_next_move.set()
        return

    ###########################################
    # user did not finish the lesson
    current_lesson = lesson_data[task_number]
    main_correct_word = None
    for w in current_lesson.values():
        if w["is_main"]:
            main_correct_word = w
            break

    main_word_stat = data.get('main_word_stat', None)
    if main_word_stat:     # so the user is redirected here due to the wrong answer
        statistic_data_main_correct_word = main_word_stat
    else:                  # so before that there were no attempts
        statistic_data_main_correct_word = {
            'sql_id': main_correct_word['word_id'],
            'current_rating': main_correct_word['rating'],
            'attempts': 0,
            'mistakes': 0
        }
    logger.info(f'{username} task {main_correct_word["word"]}')

    if task_number % 2 == 0:    # All even steps will be tasks of the type to determine the correct word description
        task_flag = 'determine the correct word description'
        answer = text(
                bold(f"{task_number + 1}."), r'Select the correct description of the word\.', '\n',
                '\n',
                bold('Word:\n'),
                '\n',
                bold(f'    "{main_correct_word["word"]}"\n'),
                '\n',
                bold('Answers:\n'),
                '\n',
                bold('    a.'), italic(f'{current_lesson.get("a")["description"]}\n'),
                '\n',
                bold('    b.'), italic(f'{current_lesson.get("b")["description"]}\n'),
                '\n',
                bold('    c.'), italic(f'{current_lesson.get("c")["description"]}\n'),
                '\n',
                bold('    d.'), italic(f'{current_lesson.get("d")["description"]}\n'),
                ' \n')

    else:    # All odd steps will be tasks of the type to define the correct word according to the description
        task_flag = 'define the correct word'
        answer = text(
                bold(f"{task_number + 1}."), r'Select the correct word by description\.', '\n',
                '\n',
                bold('Description:\n'),
                '\n',
                bold(f'    "{main_correct_word["description"]}"\n'),
                '\n',
                bold('Answers:\n'),
                '\n',
                bold('    a.'), italic(f'{current_lesson.get("a")["word"]}\n'),
                '\n',
                bold('    b.'), italic(f'{current_lesson.get("b")["word"]}\n'),
                '\n',
                bold('    c.'), italic(f'{current_lesson.get("c")["word"]}\n'),
                '\n',
                bold('    d.'), italic(f'{current_lesson.get("d")["word"]}\n'),
                ' \n')
        pass

    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2, one_time_keyboard=True)
    buttons = ['a', 'b', 'c', 'd']
    keyboard.add(*buttons)
    await call.message.answer(answer, parse_mode=ParseMode.MARKDOWN_V2, reply_markup=keyboard)

    await state.update_data(
        main_word_stat=statistic_data_main_correct_word,
        current_task=current_lesson
    )

    if task_flag == 'define the correct word':
        logger.info(f'{username} Move the user to the state of giving word-answers')
        await state.update_data(
            task_type='choose_the_word'
        )
    elif task_flag == 'determine the correct word description':
        logger.info(f'{username} Move the user to the state of giving description-answers')
        await state.update_data(
            task_type='choose_the_description'
        )

    await call.answer(show_alert=False)
    await ConductLesson.waiting_for_answer.set()


async def ms_get_answer_set_task(message: types.Message, state: FSMContext):
    """
    2 action
        set a new task or finish the lesson
    """
    username = message.from_user.username
    answer = message.text.strip().lower()
    data = await state.get_data()
    task_number = data['task_number']
    task_type = data['task_type']
    current_task = data['current_task']

    main_word_stat = data['main_word_stat']
    lesson_stats = data['lesson_stats']
    current_attempt_count = main_word_stat['attempts']
    current_mistake_count = main_word_stat['mistakes']
    current_word_rating = main_word_stat['current_rating']

    logger.info(f'{username} lesson {task_number} catch answer {answer}')

    current_attempt_count += 1

    # 0. depending on what type of task - you need to determine what is considered the correct user input and then
    # convert this input to a dictionary key
    if task_type == 'choose_the_description':
        # checking the response to the correctness of the input
        possible_answers = {"a", "b", "c", "d", "1", "2", "3", "4"}
        if answer not in possible_answers:
            logger.info(f'{username} Incorrect introduction of the answer {answer}')
            answer = text(
                emojize(':police_car: Something is wrong here'), italic(
                                    f'"{message.text if len(message.text) <= 15 else message.text[:12] + "..."}"\n'),
                '\n',
                italic('Only Latin letters: '), bold('a|b|c|d\n'),
                '\n',
                r'Try it again\, just entering your answer below\.', '\n',
                '\n'
            )
            await message.answer(answer, parse_mode=ParseMode.MARKDOWN_V2)
            return

        if answer in ("1", "2", "3", "4"):     # correct the number for the dictionary
            answer = ("a", "b", "c", "d")[int(answer) - 1]

    elif task_type == 'choose_the_word':
        standard_possible_answers = ["a", "b", "c", "d", "1", "2", "3", "4"]
        word_possible_answers = []
        for word_letter, word_data in current_task.items():     # {a: word, ...} standard
            word_possible_answers.append(word_data["word"].strip().lower())
        possible_answers = standard_possible_answers + word_possible_answers

        if answer not in possible_answers:
            logger.info(f'{username} Incorrect introduction of the answer {answer}')
            answer = text(
                emojize(':police_car: Something is wrong here'), italic(
                                    f'"{message.text if len(message.text) <= 15 else message.text[:12] + "..."}"\n'),
                '\n',
                italic('Only Latin letters: '), bold('a|b|c|d\n'),
                '\n',
                r'Try it again\, just entering your answer below\.', '\n',
                '\n'
            )
            await message.answer(answer, parse_mode=ParseMode.MARKDOWN_V2)
            return

        if answer in ("1", "2", "3", "4"):     # correct the number for the dictionary key
            answer = ("a", "b", "c", "d")[int(answer) - 1]

        if answer in word_possible_answers:    # correct the word for the dictionary key
            for key, word_data in current_task.items():
                if answer == word_data["word"].strip().lower():
                    answer = key
                    break

    # 1. the answer is received depending on what type of task it was - now it's time to check it
    user_answer_data = current_task[answer]
    if user_answer_data["is_correct"]:
        logger.info(f'{username} Correct answer {answer}')
        current_word_rating -= 1
        notification = 'Well done!,Super!,Cool!,Excellent!,' \
                       'Perfect!,Great!,Fabulous!,Correctly!,Right!'.split(',')
        answer = text(
            bold(f'{random.choice(notification)}\n'),
            bold('\n\tExample'), ' : ', italic(f'{user_answer_data["example"]}'),
            bold('\n\tWord'), ' : ', italic(f'{user_answer_data["word"]}'),
            bold('\n\tDescription'), ' : ', italic(f'{user_answer_data["description"]}'))

        inl_keyboard = types.InlineKeyboardMarkup()
        inl_buttons = [
            types.InlineKeyboardButton(text=text(emojize(':heavy_check_mark: Next')),
                                       callback_data='call_get_task'),
            types.InlineKeyboardButton(text=text(emojize(':end: Exit')), callback_data='call_cancel')]
        inl_keyboard.add(*inl_buttons)

        logger.info(f'{username} Move the user to the next question {task_number} >>> {task_number + 1}')
        await state.update_data(
            task_number=task_number + 1)
        await message.answer(answer, parse_mode=ParseMode.MARKDOWN_V2, reply_markup=inl_keyboard)

        main_word_stat['attempts'] = current_attempt_count
        main_word_stat['mistakes'] = current_mistake_count
        main_word_stat['current_rating'] = current_word_rating
        lesson_stats.append(main_word_stat)
        await state.update_data(
            main_word_stat=None,
            lesson_stats=lesson_stats
        )

        await ConductLesson.waiting_for_task.set()

    else:
        logger.info(f'{username} Incorrect answer {answer}')
        current_mistake_count += 1
        current_word_rating += 1
        notification = 'Mistakes teach!,Mistakes are the best teacher!,Dont be upset!,Incorrect answer.,' \
                       'Now you will remember this!,We learn from failure not from success!'.split(",")
        answer = text(
            bold(f'{random.choice(notification)}\n'),
            bold('\n\tExample'), ' : ', italic(f'{user_answer_data["example"]}'),
            bold('\n\tWord'), ' : ', italic(f'{user_answer_data["word"]}'),
            bold('\n\tDescription'), ' : ', italic(f'{user_answer_data["description"]}'))

        inl_keyboard = types.InlineKeyboardMarkup()
        inl_buttons = [
            types.InlineKeyboardButton(text=text(emojize(':back: Try again')),
                                       callback_data='call_get_task'),
            types.InlineKeyboardButton(text=text(emojize(':end: Exit')), callback_data='call_cancel')]
        inl_keyboard.add(*inl_buttons)

        logger.info(f'{username} Return the user to the question {task_number} >>> {task_number}')
        await message.answer(answer, parse_mode=ParseMode.MARKDOWN_V2, reply_markup=inl_keyboard)

        main_word_stat['attempts'] = current_attempt_count
        main_word_stat['mistakes'] = current_mistake_count
        main_word_stat['current_rating'] = current_word_rating
        await state.update_data(
            main_word_stat=main_word_stat
        )

        await ConductLesson.waiting_for_task.set()


async def cb_get_call_to_lesson(call: types.CallbackQuery, state: FSMContext):
    """
    3 action
        delegate work lesson_cmd coroutine
    """
    username = call.from_user.username
    logger.info(f'{username} Send call with /lesson command')

    await call.message.delete_reply_markup()
    await call.answer(show_alert=False)
    await lesson_cmd(message=call.message, state=state)


########################################################################################################################
def register_lesson_handlers(dp: Dispatcher):
    logger.info(f'| {dp} | Register lesson handlers')

    dp.register_message_handler(lesson_cmd, commands=['lesson'], state='*')

    dp.register_callback_query_handler(
        cb_get_task_number_issues_task,
        Text(equals='call_get_task'),
        state=ConductLesson.waiting_for_task
    )

    dp.register_message_handler(ms_get_answer_set_task, state=ConductLesson.waiting_for_answer)

    dp.register_callback_query_handler(
        cb_get_call_to_lesson,
        Text(equals='call_lesson'),
        state=ConductLesson.waiting_for_next_move
    )
