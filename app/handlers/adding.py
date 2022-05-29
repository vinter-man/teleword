"""
ADD WORDS TO USER DB (all skills with redis, algorithmic, aiogram, restapi)
1 Example adding (inl.button - use last) - check for min len
2 Word adding - check for min len and numeric
3 Description adding - check for min len
4 Try to category by api | parsing

back button
reset button
"""
import asyncio
import logging
import sys
import time

########################################################################################################################
logger = logging.getLogger(__name__)
logging.basicConfig(
        level=logging.INFO,
        stream=sys.stdout,
        format='[%(asctime)s]:[%(levelname)s]:[%(filename)s]:[%(lineno)d]: %(message)s',
    )


########################################################################################################################

