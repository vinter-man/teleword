import multiprocessing
import sys
import logging
import subprocess

from config.config import PYTHON_PATH


########################################################################################################################
logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    stream=sys.stdout,
    format='[%(asctime)s]:[%(levelname)s]:[%(filename)s]:[%(lineno)d]: %(message)s',
)


########################################################################################################################
api_process = multiprocessing.Process(
    target=subprocess.run,
    kwargs={
        'args': f'{PYTHON_PATH} api.py',
        'shell': True
    })


bot_process = multiprocessing.Process(
    target=subprocess.run,
    kwargs={
        'args': f'{PYTHON_PATH} bot.py',
        'shell': True
    })


########################################################################################################################
if __name__ == '__main__':
    logger.info("Starting teleword")
    api_process.start()
    bot_process.start()


