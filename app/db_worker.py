import collections
import datetime
import logging
import random
import sys
import time

import sqlalchemy
import mysql.connector

from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from sqlalchemy.orm import sessionmaker
import sqlalchemy.exc

from config.config import MY_SQL


########################################################################################################################
logger = logging.getLogger(__name__)
logging.basicConfig(
        level=logging.INFO,
        stream=sys.stdout,
        format='[%(asctime)s]:[%(levelname)s]:[%(filename)s]:[%(lineno)d]: %(message)s',
    )


########################################################################################################################
########################################################################################################################
# basic
engine = sqlalchemy.create_engine(MY_SQL, echo=True)
Base = declarative_base()    # this guy will set the trend :)


########################################################################################################################
# python classes
class Users(Base):
    __tablename__ = 'users'

    tg_id = sqlalchemy.Column(sqlalchemy.Integer, primary_key=True)
    nickname = sqlalchemy.Column(sqlalchemy.String(250), nullable=False)
    lang_code = sqlalchemy.Column(sqlalchemy.String(10), nullable=False)
    shock_mode = sqlalchemy.Column(sqlalchemy.Integer, default=0)
    is_blacklisted = sqlalchemy.Column(sqlalchemy.Boolean, default=False)
    is_bot = sqlalchemy.Column(sqlalchemy.Boolean, default=False)
    creation_time = sqlalchemy.Column(sqlalchemy.String(20), nullable=False)
    last_use_time = sqlalchemy.Column(sqlalchemy.String(20), nullable=False)
    current_use_time = sqlalchemy.Column(sqlalchemy.String(20), nullable=False)

    exxs = relationship('UsersExamples', backref='user_examples')    # class not table name
    stats = relationship('UsersStatistics', backref='user_statistics')


class UsersExamples(Base):
    __tablename__ = 'examples'

    ex_id = sqlalchemy.Column(sqlalchemy.Integer, primary_key=True, autoincrement=True, nullable=False)
    example = sqlalchemy.Column(sqlalchemy.String(400), nullable=False)
    user_tg_id = sqlalchemy.Column(sqlalchemy.Integer, sqlalchemy.ForeignKey('users.tg_id'), nullable=False)

    words = relationship('UsersExamplesWords', backref='example_words')


class UsersExamplesWords(Base):
    __tablename__ = 'words'
    word_id = sqlalchemy.Column(sqlalchemy.Integer, primary_key=True, autoincrement=True, nullable=False)
    word = sqlalchemy.Column(sqlalchemy.String(135), nullable=False)
    description = sqlalchemy.Column(sqlalchemy.String(400), nullable=False)
    category = sqlalchemy.Column(sqlalchemy.String(20))
    rating = sqlalchemy.Column(sqlalchemy.Integer, default=0)
    example_id = sqlalchemy.Column(sqlalchemy.Integer, sqlalchemy.ForeignKey('examples.ex_id'))


class UsersStatistics(Base):
    __tablename__ = 'statistics'

    day_id = sqlalchemy.Column(sqlalchemy.Integer, primary_key=True)
    day = sqlalchemy.Column(sqlalchemy.String(10), nullable=False)
    firs_try_success = sqlalchemy.Column(sqlalchemy.Integer)
    mistake = sqlalchemy.Column(sqlalchemy.Integer)
    total = sqlalchemy.Column(sqlalchemy.Integer)
    user_tg_id = sqlalchemy.Column(sqlalchemy.Integer, sqlalchemy.ForeignKey('users.tg_id'))


########################################################################################################################
# create
Base.metadata.create_all(engine)


########################################################################################################################
# work with
DbSession = sessionmaker(bind=engine)
session = DbSession()


########################################################################################################################
########################################################################################################################
# common.py functions
def is_user(telegram_id: str) -> bool:

    result = session.query(Users).filter(Users.tg_id == telegram_id).all()
    if not result:
        return False
    return True


def add_user(tg_id: int, nickname: str, lang_code: str, shock_mode: int, is_blacklisted: bool,
             is_bot: bool, creation_time: str, last_use_time: str, current_use_time: str):

    session.add(Users(
        tg_id=tg_id, nickname=nickname, lang_code=lang_code, shock_mode=shock_mode, is_blacklisted=is_blacklisted,
        is_bot=is_bot, creation_time=creation_time, last_use_time=last_use_time, current_use_time=current_use_time
    ))
    session.commit()


def change_user_last_using(user_tg_id: str):

    user = session.query(Users).filter_by(tg_id=user_tg_id).one()
    user.current_use_time = str(datetime.date.today())

    difference = datetime.date.fromisoformat(user.current_use_time) - datetime.date.fromisoformat(user.last_use_time)
    difference = int(difference.days)

    if not difference:
        logger.info(f'| {user_tg_id} | no different user using time')
    elif difference == 1:
        logger.info(f'| {user_tg_id} | shock_mode +1 day')
        user.shock_mode += 1
        user.last_use_time = user.current_use_time
    else:
        logger.info(f'| {user_tg_id} | shock_mode is finish')
        user.shock_mode = 0
        user.last_use_time = user.current_use_time

    session.add(user)
    session.commit()


def users_bl_list() -> list:
    return [i for i in session.query(Users).filter_by(is_blacklisted='True').all()]


def change_user_bl_status(user_tg_id, change_for: bool):

    user = session.query(Users).filter_by(tg_id=user_tg_id).one()

    if change_for:
        user.is_blacklisted = True
    else:
        user.is_blacklisted = False

    session.add(user)
    session.commit()
    logger.info(f'| {user_tg_id} | changed black list status to "{change_for}"')


########################################################################################################################
# adding.py functions
def add_example(example_text: str, user_tg_id: int) -> UsersExamples:
    """Adding new example to 'examples' table, return UsersExamples obj"""

    example_in = session.query(UsersExamples).filter(sqlalchemy.and_(
        UsersExamples.example == example_text,
        UsersExamples.user_tg_id == user_tg_id
    )).first()   # First result | None
    if example_in:      # no need to add
        logger.info(f'| {user_tg_id} | example already added return value')
        return example_in

    example_to_add = UsersExamples(
        example=example_text,
        user_tg_id=user_tg_id
    )
    session.add(example_to_add)
    session.commit()
    logger.info(f'| {user_tg_id} | example successfully added return value')
    return example_to_add


def add_word(word: str, description: str, category: str, rating: int, example: UsersExamples):
    """Adding new word to 'words' table"""

    word_in = session.query(UsersExamplesWords).filter(sqlalchemy.and_(
        UsersExamplesWords.word == word,
        UsersExamplesWords.description == description,
        UsersExamplesWords.example_id == example.ex_id,
    )).first()   # First result | None

    if word_in:
        logger.warning(f'| {word, example.ex_id} | word already added')
        return

    word_to_add = UsersExamplesWords(
        word=word,
        description=description,
        category=category,
        rating=rating,
        example_id=example.ex_id    # or "example_words=example"
    )
    session.add(word_to_add)
    session.commit()
    logger.info(f'| {word, example.ex_id} | word successfully added')


########################################################################################################################
# lessons.py functions
# *get id - give all the words of the user
def get_user(tg_id: int):
    return session.query(Users).filter_by(tg_id=tg_id).first()


fake = get_user(341677393993011)
my_friend = get_user(1403092873)

###########################################
time_start = time.process_time()
print('start >>> ', time_start)

me = get_user(341677011)
WordItem = collections.namedtuple('WordItem', 'tg_id, word, description, example, category, rating, word_obj')

words = [WordItem(exx.user_tg_id, word.word, word.description, exx.example, word.category, word.rating, word)
          for exx in me.exxs for word in exx.words]    # * itertools it

# words.sort(key=lambda word: word[-2])
words.sort(key=lambda word: word.rating)

# the most difficult words are better learned 1/3(5):
# 1 - 3 when repeated at the beginning (as a work on mistakes)
# 14 - 15 and as the last tasks (like a boss in a video game, so that the player has fun after passing)
difficult_words = words[:5]
random.shuffle(difficult_words)
print(f'\nDIFWORDS >>> {difficult_words}')
# The rest of the words are simple 2/3(10)
remaining_words = words[5:]
random.shuffle(remaining_words)
easy_words = remaining_words[:10]
print(f'\nEASWORDS >>> {easy_words}')

words_for_test = collections.deque(
    iterable=difficult_words[:3] + easy_words + difficult_words[3:],
    maxlen=15
)
print(f'\nDEQUE >>> {words_for_test}')


# Let's make data for the test (where there will be correct and wrong answers)
data_for_test = []
for i in range(len(words_for_test)):     # 15
    random.shuffle(words)     # I mix each time, to improve accident
    print()
    test_words = []           # 4 words, in the first place is always correct

    right_word = words_for_test.popleft()     # in order
    test_words.append(right_word)

    for word in words:
        if len(test_words) == 4:    # 4 words
            break
        if word not in test_words and word.category == right_word.category:
            # the best learning effect is when the words are not just random, but belong to the same part of speech ...
            wrong_word = word
            test_words.append(wrong_word)

    if len(test_words) != 4:     # ... but the user does not always have enough words ...
        for word in words:
            if len(test_words) == 4:
                break
            if word not in test_words:
                # therefore, fill in the missing ones in order, random.shuffle at the beginning will prevent repetitions
                wrong_word = word
                test_words.append(wrong_word)

    data_for_test.append(test_words)
    print(test_words)
    print([(i.word, i.category) for i in test_words], '\n')


print(data_for_test, '\n')    # [[(ok), (wrong), (wrong), (wrong)],[(),(),(),()],[(),(),(),()],]
print([[(i[0].word, i[0].category), (i[1].word, i[1].category), (i[2].word, i[2].category), (i[3].word, i[3].category)]
       for i in data_for_test])
########################################################
time_finish = time.process_time()
print('finish >>> ', time_finish - time_start)

########################################################################################################################
# distinct - for words working (like set in python)
# CONCAT - concatenate two or more text values and returns the concatenating string CONCAT('name', ', ', 'lastname')
# AS - SELECT CONCAT(FirstName,', ', City) AS new_column
# UPPER LOWER SQRT AVG SUM
# SUB-QUERIES >>>
# >>> SELECT FirstName, Salary FROM employees WHERE  Salary > (SELECT AVG(Salary) FROM employees) ORDER BY Salary DESC;
# all 3 relationship!
# AUTO_INCREMENT for primary keys
# The ALTER TABLE command is used to add(ADD), delete(DROP COLUMN), or modify(RENAME) columns in an existing table.
