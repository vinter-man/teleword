import logging
import sys

import sqlalchemy
import mysql.connector

from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from sqlalchemy.orm import sessionmaker

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
    shock_mode = sqlalchemy.Column(sqlalchemy.Integer)
    is_blacklisted = sqlalchemy.Column(sqlalchemy.Boolean, default=False)
    is_bot = sqlalchemy.Column(sqlalchemy.Boolean, default=False)
    creation_time = sqlalchemy.Column(sqlalchemy.String(20), nullable=False)
    last_use_time = sqlalchemy.Column(sqlalchemy.String(20), nullable=False)

    exxs = relationship('examples', backref='user_examples')
    stats = relationship('statistics', backref='user_statistics')


class UsersExamples(Base):
    __tablename__ = 'examples'

    ex_id = sqlalchemy.Column(sqlalchemy.Integer, primary_key=True)
    example = sqlalchemy.Column(sqlalchemy.String(400), nullable=False)
    user_tg_id = sqlalchemy.Column(sqlalchemy.Integer, sqlalchemy.ForeignKey('users.tg_id'))

    words = relationship('words', backref='example_words')


class UsersExamplesWords(Base):
    __tablename__ = 'words'
    word_id = sqlalchemy.Column(sqlalchemy.Integer, primary_key=True)
    word = sqlalchemy.Column(sqlalchemy.String(135), nullable=False)
    description = sqlalchemy.Column(sqlalchemy.String(400), nullable=False)
    category = sqlalchemy.Column(sqlalchemy.String(20))
    rating = sqlalchemy.Column(sqlalchemy.Integer)
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
# adding.py functions


########################################################################################################################
# distinct - for words working (like set in python)
# CONCAT - concatenate two or more text values and returns the concatenating string CONCAT('name', ', ', 'lastname')
# AS - SELECT CONCAT(FirstName,', ', City) AS new_column
# UPPER LOWER SQRT AVG SUM
# SUB-QUERIES >>>
# >>> SELECT FirstName, Salary FROM employees WHERE  Salary > (SELECT AVG(Salary) FROM employees) ORDER BY Salary DESC;
# all 3 relationship!