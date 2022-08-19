import json
import logging
import sys
import os

from flask import Flask
from flask_restful import Api, Resource, reqparse

import db_worker


########################################################################################################################
logger = logging.getLogger(__name__)
logging.basicConfig(
        level=logging.INFO,
        stream=sys.stdout,
        format='[%(asctime)s]:[%(levelname)s]:[%(filename)s]:[%(lineno)d]: %(message)s',
    )


########################################################################################################################
class Words(Resource):     # Resource - restfull king

    def get(self, token):
        try:
            sql_user = db_worker.get_user_by_api_key(token=token)
        except Exception as e:
            logger.warning(f'[{token}] Can`t find user id "{e}"')
            return {'error': 'Could not find a user with this key, please check your key and try again'}, 404
        else:
            logger.info(f'[{sql_user.nickname}] GET WORDS')
        try:
            data_path = db_worker.create_file_with_user_words(
                user_tg_id=str(sql_user.tg_id),
                file_path='../temporary',
                file_type='json',
                sql_filter_key='default',
                sql_sort_key='all my words',
            )
        except Exception as e:
            logger.error(f'[{sql_user.nickname}] Can`t made data file "{e}"')
            return {'error': 'Failed to collect words from data base for query'}, 404
        else:
            logger.info(f'[{sql_user.nickname}] WORDS DATA IN "{data_path}"')
        try:
            file = open(data_path, 'r', encoding='utf-8')
            data = json.load(file)
        except Exception as e:
            logger.error(f'[{sql_user.nickname}] Can`t load json file "{e}"')
            return {'error': 'Failed to collect words from temporary file for query'}, 404
        else:
            file.close()
            os.remove(data_path)
            logger.info(f'[{sql_user.nickname}] SUCCESS GET WORDS')
            return data


########################################################################################################################
########################################################################################################################
if __name__ == '__main__':
    app = Flask(__name__)
    api = Api(app)
    api.add_resource(Words, '/api/words/<string:token>')
    api.init_app(app)
    app.run(
        debug=True,
        port=3000,
        host='127.0.0.1'
    )


# get_lesson ->

# delete_word {'word_id'}
# post_word {word": "treated", "description": "...", "example": "..."}
# put_word_or_description {'word_id': '...', word": "treated", "description": "..."}

# put_example {"example_id": "...",  "example": "..."}
# delete_example {"example_id"}

