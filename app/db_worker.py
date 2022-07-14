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

    user_id = sqlalchemy.Column(sqlalchemy.Integer, primary_key=True, autoincrement=True, nullable=False)
    tg_id = sqlalchemy.Column(sqlalchemy.String(20))
    nickname = sqlalchemy.Column(sqlalchemy.String(250), nullable=False)
    lang_code = sqlalchemy.Column(sqlalchemy.String(10), nullable=False)
    shock_mode = sqlalchemy.Column(sqlalchemy.Integer, default=0)
    points = sqlalchemy.Column(sqlalchemy.Integer, default=0)
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
    user_id = sqlalchemy.Column(sqlalchemy.Integer, sqlalchemy.ForeignKey('users.user_id'), nullable=False)

    words = relationship('UsersExamplesWords', backref='example_words')


class UsersExamplesWords(Base):
    __tablename__ = 'words'
    # word_id - sqlalchemy.Integer -> max 350000 users with 6000 words
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
    user_id = sqlalchemy.Column(sqlalchemy.Integer, sqlalchemy.ForeignKey('users.user_id'))


########################################################################################################################
# create
Base.metadata.create_all(engine)

########################################################################################################################
# work with
DbSession = sessionmaker(bind=engine)
session = DbSession()


########################################################################################################################
########################################################################################################################
# common.py
def is_user(telegram_id: str) -> bool:

    result = session.query(Users).filter(Users.tg_id == telegram_id).all()
    if not result:
        return False
    return True


def add_user(tg_id: str, nickname: str, lang_code: str, shock_mode: int,
             points: int, is_blacklisted: bool, is_bot: bool, creation_time: str,
             last_use_time: str, current_use_time: str):

    session.add(Users(
        tg_id=tg_id, nickname=nickname, lang_code=lang_code,
        shock_mode=shock_mode, points=points, is_blacklisted=is_blacklisted,
        is_bot=is_bot, creation_time=creation_time,
        last_use_time=last_use_time, current_use_time=current_use_time
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


def change_user_bl_status(user_tg_id: str, change_for: bool):

    user = session.query(Users).filter_by(tg_id=user_tg_id).one()

    if change_for:
        user.is_blacklisted = True
    else:
        user.is_blacklisted = False

    session.add(user)
    session.commit()
    logger.info(f'| {user_tg_id} | changed black list status to "{change_for}"')


########################################################################################################################
# adding.py
def add_example(example_text: str, user_tg_id: str) -> UsersExamples:
    """Adding new example to 'examples' table, return UsersExamples obj"""

    user = get_user(tg_id=user_tg_id)
    user_id = user.user_id

    example_in = session.query(UsersExamples).filter(sqlalchemy.and_(
        UsersExamples.example == example_text,
        UsersExamples.user_id == user_id
    )).first()   # First result | None
    if example_in:      # no need to add
        logger.info(f'| {user_tg_id} | example already added return value')
        return example_in

    example_to_add = UsersExamples(
        example=example_text,
        user_id=user_id
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
# lessons.py
def get_user(tg_id: str) -> Users | None:
    return session.query(Users).filter_by(tg_id=tg_id).first()


def get_word(word_id: int) -> UsersExamplesWords | None:
    return session.query(UsersExamplesWords).filter_by(word_id=word_id).first()


def change_rating(word_id: int, new_rating: int):
    word = get_word(word_id)

    if not word:
        logger.warning(f'| {word_id} | no word with user word_id')
        raise KeyError(f'{word_id}')

    old_rating = word.rating
    word.rating = new_rating
    session.add(word)
    session.commit()
    logger.info(f'changed word rating {old_rating} >>> {new_rating}')


def add_or_change_day_stat(tg_id: str, first_try: int, mistakes: int, points=15):
    today = str(datetime.date.today())
    user = get_user(tg_id=tg_id)
    user_id = user.user_id

    day_stat_log = session.query(UsersStatistics).filter(sqlalchemy.and_(
        UsersStatistics.user_id == user_id,
        UsersStatistics.day == today
    )).first()

    if day_stat_log:
        day_stat_log.firs_try_success += first_try
        day_stat_log.mistake += mistakes
        day_stat_log.total += points
        logger.info(f'change day stat f_try {first_try}, mistakes {mistakes}, total {points}...')
    else:
        day_stat_log = UsersStatistics(
            day=today,
            firs_try_success=first_try,
            mistake=mistakes,
            total=points,
            user_id=user_id
        )
        logger.info(f'add day stat f_try {first_try}, mistakes {mistakes}, total {points}...')

    user.points += points

    session.add(day_stat_log)
    session.add(user)
    session.commit()
    logger.info(f'successes add_or_change_day_stat and changing total user points')


########################################################################################################################
# statistic.py
def word_count(user_tg_id: str) -> int:
    user = get_user(tg_id=user_tg_id)
    count = 0
    for example in user.exxs:
        for word in example.words:
            count += 1
    return count


def get_user_stat(user_tg_id: str, limit: int = 7) -> list:
    return list(session.query(UsersStatistics).filter_by(user_id=get_user(user_tg_id).user_id).limit(limit))


def build_total_mistakes_firsttry_data_for_graph(user_sql_logs: list, future_length: int = 7) -> dict:

    result_dict = {
        "total": [0] * future_length,
        "mistakes": [0] * future_length,
        "first_try": [0] * future_length
    }

    today = datetime.date.today()
    for stat in user_sql_logs:
        stat_date = datetime.date.fromisoformat(stat.day)
        difference = today - stat_date
        difference = int(difference.days)
        if difference > future_length:     # old record
            continue
        else:
            place = (future_length - difference) - 1
            result_dict.get("total")[place] = stat.total
            result_dict.get("mistakes")[place] = stat.mistake
            result_dict.get("first_try")[place] = stat.firs_try_success

    return result_dict


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
