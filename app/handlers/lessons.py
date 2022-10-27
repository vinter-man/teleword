import logging
import sys
import random

from aiogram import Dispatcher, types
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.utils.markdown import text, bold, italic
from aiogram.utils.emoji import emojize
from aiogram.types import ParseMode, ChatActions
from aiogram.dispatcher.filters import Text

from .. import db_worker
from ..db_worker import MinLenError
import config


########################################################################################################################
logger = logging.getLogger(__name__)
logging.basicConfig(
        level=logging.INFO,
        stream=sys.stdout,
        format='[%(asctime)s]:[%(levelname)s]:[%(filename)s]:[%(lineno)d]: %(message)s',
    )


########################################################################################################################
class ConductLesson(StatesGroup):
    """
    Stateful class for creating the logic of forming a lesson - conducting tests - calculating the result
    """
    waiting_for_answer = State()
    waiting_for_task = State()
    waiting_for_next_move = State()


########################################################################################################################
async def lesson_cmd(message: types.Message, state: FSMContext):
    """
    0 action
        instruction
    """
    username = message.from_user.username
    logger.info(f'[{username}]: Start lesson')
    await state.reset_state(with_data=False)

    answer = text(
        emojize(r":person_in_lotus_position: Wait until we prepare a lesson for you \- it can take some time\.\.\."))
    remove_keyboard = types.ReplyKeyboardRemove()
    await message.answer(answer, parse_mode=ParseMode.MARKDOWN_V2, reply_markup=remove_keyboard)

    await message.bot.send_chat_action(message.from_user.id, ChatActions.TYPING)  # comfortable waiting

    db_worker.pending_rollback(username=message.from_user.username)

    try:
        lesson_data = db_worker.get_lesson_data(str(message.chat.id))
    except MinLenError as e:
        logger.info(f'[{username}]: Not enough words for lesson')
        answer = text(
                emojize(":cop: You need at least"), bold("15"), "words to start a lesson, you have only",
                bold(f"{e}."))
        await message.answer(answer, parse_mode=ParseMode.MARKDOWN_V2)
        answer = text(
                emojize(":thinking_face:"), r"The bot has 15 initial words, you can add them by clicking on the button below, "
                                  r"and then manually delete them when you no longer need them\.",
                bold(f"{e}."))
        inl_keyboard = types.InlineKeyboardMarkup()
        inl_buttons = [
            types.InlineKeyboardButton(text=text(emojize(':genie: Add')), callback_data='call_add_init_words'),
            types.InlineKeyboardButton(text=text(emojize(':no_good: I do not need it')), callback_data='call_cancel')]
        inl_keyboard.add(*inl_buttons)

        await message.answer(answer, parse_mode=ParseMode.MARKDOWN_V2, reply_markup=inl_keyboard)
        return
    except Exception as e:
        logger.error(f'[{username}]: Houston, we have got a problem {e}')
        answer = text(
                emojize(":oncoming_police_car:"), r"There was a big trouble when compiling your test\, "
                                                              r"please try again and then write to the administrator\.")
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
        main_word_stat=None,
    )

    logger.info(f'[{username}]: Transfer user to the lesson')
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
    logger.info(f'[{username}]: Lesson {task_number}')

    ###########################################
    # user reached the end and ended the lesson
    if task_number == 15:
        logger.info(f'[{username}]: Finish lesson')

        answer = text(
            bold('You have successfully coped!\n'),
            emojize(r':man_scientist: Give me a little time to calculate your result\.\.\.'), '\n')

        remove_keyboard = types.ReplyKeyboardRemove()

        await call.message.answer(answer, parse_mode=ParseMode.MARKDOWN_V2, reply_markup=remove_keyboard)
        await call.message.bot.send_chat_action(call.from_user.id, ChatActions.TYPING)

        db_worker.pending_rollback(username=call.from_user.username)

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
                logger.error(f'[{username}]: Sql error {e}')
            except Exception as e:
                logger.error(f'[{username}]: Unknown sql error {e}')

        await call.message.bot.send_chat_action(call.from_user.id, ChatActions.TYPING)
        success_percentage = int((first_try / 15) * 100)

        # daily statistics
        try:
            db_worker.add_or_change_day_stat(
                tg_id=str(call.message.chat.id),
                first_try=first_try,
                mistakes=mistakes,
            )
        except Exception as e:
            logger.error(f'[{username}]: Unknown sql error {e}')

        # shock mode
        try:
            db_worker.change_user_last_using(
                user_tg_id=str(call.message.chat.id),
                flag='change'
            )
        except Exception as e:
            logger.error(f'[{username}]: Unknown sql error {e}')

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
    logger.info(f'[{username}] Task {main_correct_word["word"]}')

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
        logger.info(f'[{username}]: Move the user to the state of giving word-answers')
        await state.update_data(
            task_type='choose_the_word'
        )
    elif task_flag == 'determine the correct word description':
        logger.info(f'[{username}]: Move the user to the state of giving description-answers')
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

    logger.info(f'[{username}]: Lesson {task_number} catch answer {answer}')

    current_attempt_count += 1

    # 0. depending on what type of task - you need to determine what is considered the correct user input and then
    # convert this input to a dictionary key
    async def toha_egg(message):
        answer = text(
            bold('Congratulations, you found an Easter egg!'), emojize(':egg:'), '\n',
            '\n',
            r'I dedicate it to the first person who found it as a bug\.', '\n',
            '\n',
            r'Toha\, brother\, thank you for always helping me\, never turning away\.'
            r' I hope we can get out of the current ugly situation\. I hope we meet more than once and'
            r' we will have the heat like on Bora\-Bora not this cold and hopelessness',
            emojize(':beach_with_umbrella:'), '\n'
        )
        await message.answer_photo(
            photo=open(r'img/project_images/temporary/temp261022.png', 'rb'),
            caption=answer,
            parse_mode=ParseMode.MARKDOWN_V2
        )
        await message.bot.send_audio(
            chat_id=message.chat.id,
            audio=open(r'img/project_images/temporary/temp261022.mp3', 'rb')
        )

    if task_type == 'choose_the_description':
        # checking the response to the correctness of the input
        possible_answers = {"a", "b", "c", "d", "1", "2", "3", "4"}
        if answer not in possible_answers:
            if answer == 'a|b|c|d':
                await toha_egg(message)
                return
            logger.info(f'[{username}]: Incorrect introduction of the answer {answer}')
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
            if answer == 'a|b|c|d':
                await toha_egg(message)
                return
            logger.info(f'[{username}]: Incorrect introduction of the answer {answer}')
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
        logger.info(f'[{username}]: Correct answer {answer}')
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

        logger.info(f'[{username}]: Move the user to the next question {task_number} >>> {task_number + 1}')
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
        logger.info(f'[{username}]: Incorrect answer {answer}')
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

        logger.info(f'[{username}]: Return the user to the question {task_number} >>> {task_number}')
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
    logger.info(f'[{username}]: Send call with /lesson command')

    await call.message.delete_reply_markup()
    await call.answer(show_alert=False)
    await lesson_cmd(message=call.message, state=state)


async def cb_get_call_to_add_init_words(call: types.CallbackQuery, state: FSMContext):
    """
    independent action
        adds words from the config dictionary to the user
    """
    username = call.from_user.username
    logger.info(f'[{username}]: Send call with "add_init_words" command')
    await state.reset_state(with_data=False)

    answer = text(
        emojize(r':package: I add words, need a little time\.\.\.'), '\n')
    remove_keyboard = types.ReplyKeyboardRemove()

    await call.message.answer(answer, parse_mode=ParseMode.MARKDOWN_V2, reply_markup=remove_keyboard)
    await call.message.bot.send_chat_action(call.from_user.id, ChatActions.TYPING)

    db_worker.pending_rollback(username)

    try:
        for word_data in config.config.INIT_WORDS:
            user_example = db_worker.add_example(
                example_text=word_data["example"],
                user_tg_id=str(call.message.chat.id)
            )
            user_word = db_worker.add_word(
                word=word_data["word"],
                description=word_data["description"],
                category=word_data["category"],
                rating=0,
                example=user_example,
            )
            logger.info(f'[{username}]: >>> {word_data["word"]}')
    except Exception as e:
        logger.error(f'[{username}]: Houston, we have got a problem {e}')
        answer = text(
                emojize(":oncoming_police_car:"), r"There was a big trouble when add your initial words\, "
                                                              r"please try again and then write to the administrator\.")
        await call.message.answer(answer, parse_mode=ParseMode.MARKDOWN_V2)
        return

    answer = text(
        emojize(r':ski: Done, now you have 15 starting words'), '\n')

    await call.message.answer(answer, parse_mode=ParseMode.MARKDOWN_V2)
    await call.message.delete_reply_markup()
    await call.answer(show_alert=False)

    logger.info(f'[{username}]: Add init words success')


########################################################################################################################
def register_lesson_handlers(dp: Dispatcher):
    """
    The function serves as a register of all the module coroutines in the correct sequence
     (used instead of decorators to create a more readable structure)
    """
    logger.info(f'[{dp}]: Register lesson handlers')

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

    dp.register_callback_query_handler(
        cb_get_call_to_add_init_words,
        Text(equals='call_add_init_words'),
        state='*'
    )

