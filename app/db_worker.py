import datetime
import logging
import sys

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

    exxs = relationship('examples', backref='user_examples')
    stats = relationship('statistics', backref='user_statistics')


class UsersExamples(Base):
    __tablename__ = 'examples'

    ex_id = sqlalchemy.Column(sqlalchemy.Integer, primary_key=True, autoincrement=True, nullable=False)
    example = sqlalchemy.Column(sqlalchemy.String(400), nullable=False)
    user_tg_id = sqlalchemy.Column(sqlalchemy.Integer, sqlalchemy.ForeignKey('users.tg_id'))

    words = relationship('words', backref='example_words')


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
def add_example(example_text: str, user_tg_id: str) -> UsersExamples:
    """Adding new example to 'examples' table, return UsersExamples obj"""

    example_in = session.query(UsersExamples).filter(sqlalchemy.and_(
        UsersExamples.example == example_text,
        UsersExamples.user_tg_id == user_tg_id
    )).firtst()    # First result | None
    if example_in:    # no need to add
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
    )).firtst()    # First result | None

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
# distinct - for words working (like set in python)
# CONCAT - concatenate two or more text values and returns the concatenating string CONCAT('name', ', ', 'lastname')
# AS - SELECT CONCAT(FirstName,', ', City) AS new_column
# UPPER LOWER SQRT AVG SUM
# SUB-QUERIES >>>
# >>> SELECT FirstName, Salary FROM employees WHERE  Salary > (SELECT AVG(Salary) FROM employees) ORDER BY Salary DESC;
# all 3 relationship!
# AUTO_INCREMENT for primary keys
# The ALTER TABLE command is used to add(ADD), delete(DROP COLUMN), or modify(RENAME) columns in an existing table.
