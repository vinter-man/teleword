"""
CHECKING STATISTIC (all mysql skills)
1 print list where
(calendar(date, first try successes, mistakes, total words repeated ), shock_mode counter, 3 most important words)
"""

# * When the user calls the statistics command - we collect all his statistical records - we determine what the date is
# today - for all records older than today - 31 days from our number we delete - then we print a graph with 31 / 7 cells
# for days (how many points are in the cell, the upper rectangle, two lower rectangles first attempt | error)
# total points ever shock mode ever when start

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


########################################################################################################################
def register_handlers_common(dp: Dispatcher, admin_id: int):
    logger.info(f'| {dp, admin_id} | Register statistic handlers')

