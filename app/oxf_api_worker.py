import requests
import logging
import sys

from config.config import APP_KEY_OXF, APP_ID_OXF, URL_OXF


########################################################################################################################
logger = logging.getLogger(__name__)
logging.basicConfig(
        level=logging.INFO,
        stream=sys.stdout,
        format='[%(asctime)s]:[%(levelname)s]:[%(filename)s]:[%(lineno)d]: %(message)s',
    )


########################################################################################################################
def get_word_category(word: str, default='-', url=URL_OXF) -> str:
    url += word.lower()
    headers = {
        'app_id': APP_ID_OXF,
        'app_key': APP_KEY_OXF
    }
    r = requests.get(url, headers=headers)
    if r.status_code != 200:
        logger.warning(f'{word} Requests error '
                       f'{r.status_code, headers, url} \n {r.text} \n ')
        return default

    word_data = r.json()
    if "error" in word_data.keys():
        logger.warning(f'{word} No entry found that matches the provided data'
                       f'{r.status_code, headers, url} \n {r.text} \n ')
        return default

    # Noun | Verb ... (Part of speech)
    return word_data["results"][0]["lexicalEntries"][0]["lexicalCategory"]["text"]