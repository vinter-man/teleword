import logging
import sys
import time


# ======================================================================================================================
# logging ==============================================================================================================
l = logging.getLogger('loger')
l.setLevel(logging.INFO)

handler = logging.StreamHandler(stream=sys.stdout)
handler.setFormatter(logging.Formatter(fmt=
                                       '[%(asctime)s]:[%(levelname)s]:[%(filename)s]:[%(lineno)d]: %(message)s'))
l.addHandler(handler)


def dis():
    logging.disable()


# ======================================================================================================================
# Test times ===========================================================================================================
def flag_strt():
    strt = time.time()
    l.info(f'Start: {strt}')
    return strt


def flag_fnsh(strt):
    fnsh = time.time()
    l.info(f'Finish: {fnsh}')
    l.info(f'Time: {fnsh-strt}')
    return fnsh-strt


def time_percent(flag1: float, flag2: float):
    x = (flag1 / flag2) * 100
    if x >= 100:
        more_or_less = 'more'
        x -= 100
    else:
        more_or_less = 'less'
        x = abs(x - 100)
    l.info(f'1 {round(flag1, 4)} on {round(x, 4)} % {more_or_less} 2 {round(flag2, 4)}')
