import multiprocessing
import sys
import logging
import subprocess
import time

from app import db_worker
from config.config import PYTHON_PATH
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
    while True:

        for process in processes:
            if not process.is_alive():
                logger.warning(f'[{process.name}] Process {process.pid} is dead. I am trying to resurrect')
                try:
                    process.start()
                except Exception as e:
                    logger.error(f'[{process.name}] Failed to reanimate the process {process.pid} {e}. Going to sleep')
            else:
                logger.info(f'[{process.name}] Process {process.pid} is alive. Going to sleep')

        try:
            db_worker.session.commit()
        except:
            db_worker.session.rollback()
        finally:
            db_worker.session.close()

        if not is_connection_alive():
            for process in processes:
                process.stop()
                process.join()
                process.start()

        time.sleep(900)


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
    logger.info("Starting teleword")
    api_process.start()
    bot_process.start()
    status_checker([api_process, bot_process])
