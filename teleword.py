import multiprocessing
import sys
import logging
import subprocess
import time
import requests

from config.config import PYTHON_PATH, ADMIN_API_KEY
from app.db_worker import is_connection_alive


########################################################################################################################
logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    stream=sys.stdout,
    format='[%(asctime)s]:[%(levelname)s]:[%(filename)s]:[%(lineno)d]: %(message)s',
)


########################################################################################################################
def status_checker(processes: list):
    """
    Resurrects all processes from the processes list
    :param processes: List of multiprocessing.Process processes
    """
    h = 0
    while True:

        for process in processes:
            if not process.is_alive():
                logger.warning(f'[{process.name}] Process {process.pid} is dead. I am trying to resurrect')
                try:
                    process.start()
                except Exception as e:
                    logger.error(f'[{process.name}] Failed to reanimate the process {process.pid} {e}. Going to sleep')

        if not is_connection_alive():
            for process in processes:
                process.stop()
                process.join()
                process.start()

        try:
            r = requests.get(f'http://localhost/api/lesson/{ADMIN_API_KEY}')
            if r.status_code != 200:
                raise ConnectionError(f'{r.status_code, r.json(), r.text}')
        except Exception as e:
            logger.error(f'[{h}] Failed to make request \n\n{e}\n\n I am trying to resurrect...')
            for process in processes:
                process.stop()
                process.join()
                process.start()

        h += 1
        time.sleep(3)


########################################################################################################################
api_process = multiprocessing.Process(
    target=subprocess.run,
    kwargs={
        'args': f'{PYTHON_PATH} api.py',
        'shell': True
    },
    name="api_process"
)

bot_process = multiprocessing.Process(
    target=subprocess.run,
    kwargs={
        'args': f'{PYTHON_PATH} bot.py',
        'shell': True,
    },
    name="bot_process"
)


########################################################################################################################
if __name__ == '__main__':     # Runs an entire two-part application by two different processes
    logger.info(": Starting teleword")
    api_process.start()
    bot_process.start()
    status_checker([api_process, bot_process])
