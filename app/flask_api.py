import json
import logging
import sys
import os

from flask import Flask
from flask import request as frequest
from flask import jsonify
from flask_restful import Api, Resource, reqparse

import db_worker

from config.config import HOST


########################################################################################################################
logger = logging.getLogger(__name__)
logging.basicConfig(
        level=logging.INFO,
        stream=sys.stdout,
        format='[%(asctime)s]:[%(levelname)s]:[%(filename)s]:[%(lineno)d]: %(message)s',
    )


########################################################################################################################
app = Flask(__name__)
api = Api(app)


########################################################################################################################
class LengthError(TypeError):
    """
    It called when the length of the data is not within the constraints
    """


class AccessError(TypeError):
    """
    It called when the user tries to access objects that do not belong to him.
    """


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
            return data, 200


class Lesson(Resource):

    def get(self, token):

        try:
            sql_user = db_worker.get_user_by_api_key(token=token)
        except Exception as e:
            logger.warning(f'[{token}] Can`t find user id "{e}"')
            return {'error': 'Could not find a user with this key, please check your key and try again'}, 404
        else:
            logger.info(f'[{sql_user.nickname}] GET LESSON')

        try:
            data = db_worker.get_lesson_data(tg_id=sql_user.tg_id)
        except db_worker.MinLenError as e:
            logger.error(f'[{sql_user.nickname}] Can`t make data file "{e}"')
            return {'error': f'Not enough words for lesson. You have {e}, minimum 15'}, 404
        except Exception as e:
            logger.error(f'[{sql_user.nickname}] Can`t make data file "{e}"')
            return {'error': 'Failed to collect lesson from data base for query'}, 404
        else:
            logger.info(f'[{sql_user.nickname}] LESSON DATA ({len(data)})')
            logger.info(f'[{sql_user.nickname}] SUCCESS GET LESSON')
            return data, 200


class Example(Resource):

    def get(self, token, example_id):

        try:
            sql_user = db_worker.get_user_by_api_key(token=token)
        except Exception as e:
            logger.warning(f'[{token}] Can`t find user id "{e}"')
            return {'error': 'Could not find a user with this key, please check your key and try again'}, 404
        else:
            logger.info(f'[{sql_user.nickname}] GET EXAMPLE')

        try:
            sql_example = db_worker.get_example(example_id)
            if not sql_example.user_id == sql_user.user_id:
                raise AccessError
        except AccessError as e:
            logger.error(f'[{sql_user.nickname}] Can`t get data. Access denied "{e}"')
            return {'error': f'A user with such a token does not have access rights to an example with this id'}, 404
        except Exception as e:
            logger.error(f'[{sql_user.nickname}] Can`t write data "{e}"')
            return {'error': 'Failed to process your example object - check the correctness of the form data'}, 404
        else:
            logger.info(f'[{sql_user.nickname}] EXAMPLE IS READY TO BE RETURNED')

        try:
            returned_data = {
               'ex_id': sql_example.ex_id,
               'example': sql_example.example,
               'user_id': sql_example.user_id
            }
        except Exception as e:
            logger.error(f'[{sql_user.nickname}] Can`t write data from sql "{e}"')
            return {'error': 'Failed to process your example object - check the correctness of the form data'}, 404
        else:
            logger.info(f'[{sql_user.nickname}] SUCCESS GET EXAMPLE')
            return returned_data, 200

    def post(self, token, example_id):

        try:
            sql_user = db_worker.get_user_by_api_key(token=token)
        except Exception as e:
            logger.warning(f'[{token}] Can`t find user id "{e}"')
            return {'error': 'Could not find a user with this key, please check your key and try again'}, 404
        else:
            logger.info(f'[{sql_user.nickname}] POST EXAMPLE')

        try:
            new_example_data = frequest.form.to_dict()
            example = new_example_data['example']
            example_len = len(example)
            if example_len > 400 or example_len < 5:
                raise LengthError(f"{example_len}")
        except LengthError as e:
            logger.error(f'[{sql_user.nickname}] Can`t write data. Wrong length "{e}"')
            return {'error': f'Not right length for example. You have {e}, min 5 - max 400'}, 404
        except Exception as e:
            logger.error(f'[{sql_user.nickname}] Can`t write data "{e}"')
            return {'error': 'Failed to process your example object - check the correctness of the form data'}, 404
        else:
            logger.info(f'[{sql_user.nickname}] EXAMPLE IS READY TO BE RECORDED')

        try:
            sql_example = db_worker.add_example(
                example_text=example,
                user_tg_id=sql_user.tg_id
            )
        except Exception as e:
            logger.error(f'[{sql_user.nickname}] Can`t write data to sql "{e}"')
            return {'error': 'Failed to process your example object - check the correctness of the form data'}, 404
        else:
            logger.info(f'[{sql_user.nickname}] SUCCESS POST EXAMPLE')
            return {
               'ex_id': sql_example.ex_id,
               'example': sql_example.example,
               'user_id': sql_example.user_id
            }, 200

    def put(self, token, example_id):

        try:
            sql_user = db_worker.get_user_by_api_key(token=token)
        except Exception as e:
            logger.warning(f'[{token}] Can`t find user id "{e}"')
            return {'error': 'Could not find a user with this key, please check your key and try again'}, 404
        else:
            logger.info(f'[{sql_user.nickname}] PUT EXAMPLE')

        try:
            sql_example = db_worker.get_example(example_id=example_id)
            new_example_data = frequest.form.to_dict()
            example = new_example_data['example']
            example_len = len(example)
            if example_len > 400 or example_len < 5:
                raise LengthError(f"{example_len}")
            if not sql_example.user_id == sql_user.user_id:
                raise AccessError
        except LengthError as e:
            logger.error(f'[{sql_user.nickname}] Can`t write data. Wrong length "{e}"')
            return {'error': f'Not right length for example. You have {e}, min 5 - max 400'}, 404
        except AccessError as e:
            logger.error(f'[{sql_user.nickname}] Can`t get data. Access denied "{e}"')
            return {'error': f'A user with such a token does not have access rights to an example with this id'}, 404
        except Exception as e:
            logger.error(f'[{sql_user.nickname}] Can`t write data "{e}"')
            return {'error': 'Failed to process your example object - check the correctness of the form data'}, 404
        else:
            logger.info(f'[{sql_user.nickname}] EXAMPLE IS READY TO BE EDIT')

        try:
            db_worker.update_data(
                data_type='example',
                data_id=sql_example.ex_id,
                new_data=example
            )
            sql_example = db_worker.get_example(
                example_id=sql_example.ex_id
            )
            returned_data = {
                'ex_id': sql_example.ex_id,
                'example': sql_example.example,
                'user_id': sql_example.user_id
            }
        except Exception as e:
            logger.error(f'[{sql_user.nickname}] Can`t write data from sql "{e}"')
            return {'error': 'Failed to process your example object - check the correctness of the form data'}, 404
        else:
            logger.info(f'[{sql_user.nickname}] SUCCESS PUT EXAMPLE')
            return returned_data, 200

    def delete(self, token, example_id):

        try:
            sql_user = db_worker.get_user_by_api_key(token=token)
        except Exception as e:
            logger.warning(f'[{token}] Can`t find user id "{e}"')
            return {'error': 'Could not find a user with this key, please check your key and try again'}, 404
        else:
            logger.info(f'[{sql_user.nickname}] DELETE EXAMPLE')

        try:
            sql_example = db_worker.get_example(example_id=example_id)
            if not sql_example.user_id == sql_user.user_id:
                raise AccessError
        except AccessError as e:
            logger.error(f'[{sql_user.nickname}] Can`t delete data. Access denied "{e}"')
            return {'error': f'A user with such a token does not have access rights to an example with this id'}, 404
        except Exception as e:
            logger.error(f'[{sql_user.nickname}] Can`t write data "{e}"')
            return {'error': 'Failed to process your example object - check the correctness of the form data'}, 404
        else:
            logger.info(f'[{sql_user.nickname}] EXAMPLE IS READY TO BE DELETED')

        try:
            db_worker.delete_data(
                data_type='example',
                data_id=example_id
            )
            sql_example = db_worker.get_example(example_id)
            returned_data = {
                'success': 'Your data has been successfully deleted'
            }
            if sql_example:
                raise RuntimeError('Data was not successfully deleted from sql table')
        except RuntimeError as e:
            logger.error(f'[{sql_user.nickname}] Can`t delete data from sql "{e}"')
            return {'error': 'Data was not successfully deleted from table, problem on our end, please try again'}, 404
        except Exception as e:
            logger.error(f'[{sql_user.nickname}] Can`t delete data from sql "{e}"')
            return {'error': 'Failed to process your example object - check the correctness of the data id'}, 404
        else:
            logger.info(f'[{sql_user.nickname}] SUCCESS DELETE EXAMPLE')
            return returned_data, 200


class Word(Resource):

    def get(self, token, word_id):

        try:
            sql_user = db_worker.get_user_by_api_key(token=token)
        except Exception as e:
            logger.warning(f'[{token}] Can`t find user id "{e}"')
            return {'error': 'Could not find a user with this key, please check your key and try again'}, 404
        else:
            logger.info(f'[{sql_user.nickname}] GET WORD')

        try:
            sql_word = db_worker.get_word(word_id)
            sql_example = db_worker.get_example(sql_word.example_id)
            if not sql_example.user_id == sql_user.user_id:
                raise AccessError
        except AccessError as e:
            logger.error(f'[{sql_user.nickname}] Can`t get data. Access denied "{e}"')
            return {'error': f'A user with such a token does not have access rights to an word with this id'}, 404
        except Exception as e:
            logger.error(f'[{sql_user.nickname}] Can`t write data "{e}"')
            return {'error': 'Failed to process your word object - check the correctness of the form data'}, 404
        else:
            logger.info(f'[{sql_user.nickname}] WORD IS READY TO BE RETURNED')

        try:
            returned_data = {
                'word_id': sql_word.word_id,
                'word': sql_word.word,
                'description': sql_word.description,
                'example_id': sql_word.example_id
            }
        except Exception as e:
            logger.error(f'[{sql_user.nickname}] Can`t write data from sql "{e}"')
            return {'error': 'Failed to process your word object - check the correctness of the form data'}, 404
        else:
            logger.info(f'[{sql_user.nickname}] SUCCESS GET WORD')
            return returned_data, 200

    def post(self, token, word_id):

        try:
            sql_user = db_worker.get_user_by_api_key(token=token)
        except Exception as e:
            logger.warning(f'[{token}] Can`t find user id "{e}"')
            return {'error': 'Could not find a user with this key, please check your key and try again'}, 404
        else:
            logger.info(f'[{sql_user.nickname}] POST WORD')

        try:
            new_word_data = frequest.form.to_dict()
            word = new_word_data['word']
            word_len = len(word)
            description = new_word_data['description']
            description_len = len(description)
            example_id = int(new_word_data['ex_id'])
            sql_example = db_worker.get_example(example_id)
            if not sql_example.user_id == sql_user.user_id:
                raise AccessError(f'Data owner: {sql_example.user_id}, Query owner: {sql_user.user_id}')
            if word_len > 135 or word_len < 1:
                raise LengthError(f"{word_len}")
            if description_len > 400 or description_len < 1:
                raise LengthError(f"{description_len}")
        except LengthError as e:
            logger.error(f'[{sql_user.nickname}] Can`t write data. Wrong length "{e}"')
            return {'error': f'Not right length for word or description. You have {e},'
                                                                 f' min 1 - max 135(word) | max 400(description)'}, 404
        except AccessError as e:
            logger.error(f'[{sql_user.nickname}] Can`t write data. Access denied "{e}"')
            return {'error': f'A user with such a token does not have access rights to an example with this id'}, 404
        except Exception as e:
            logger.error(f'[{sql_user.nickname}] Can`t write data "{e}"')
            return {'error': 'Failed to process your word object - check the correctness of the form data'}, 404
        else:
            logger.info(f'[{sql_user.nickname}] WORD IS READY TO BE RECORDED')

        try:
            sql_word = db_worker.add_word(
                word=word,
                description=description,
                category=db_worker.get_word_category(word),
                rating=0,
                example=sql_example
            )
        except Exception as e:
            logger.error(f'[{sql_user.nickname}] Can`t write data to sql "{e}"')
            return {'error': 'There was a problem on our side, please try again later'}, 404
        else:
            logger.info(f'[{sql_user.nickname}] SUCCESS POST WORD')
            return {
                       'word_id': sql_word.word_id,
                       'word': sql_word.word,
                       'description': sql_word.description,
                       'example_id': sql_word.example_id
                   }, 200

    def put(self, token, word_id):

        try:
            sql_user = db_worker.get_user_by_api_key(token=token)
        except Exception as e:
            logger.warning(f'[{token}] Can`t find user id "{e}"')
            return {'error': 'Could not find a user with this key, please check your key and try again'}, 404
        else:
            logger.info(f'[{sql_user.nickname}] PUT WORD')

        try:
            sql_word = db_worker.get_word(word_id=word_id)
            sql_example = db_worker.get_example(example_id=int(sql_word.example_id))
            new_word_data = frequest.form.to_dict()
            word = new_word_data['word']
            word_len = len(word)
            description = new_word_data['description']
            description_len = len(description)
            if not sql_example.user_id == sql_user.user_id:
                raise AccessError(f'Data owner: {sql_example.user_id}, Query owner: {sql_user.user_id}')
            if word_len > 135 or word_len < 1:
                raise LengthError(f"{word_len}")
            if description_len > 400 or description_len < 1:
                raise LengthError(f"{description_len}")
        except LengthError as e:
            logger.error(f'[{sql_user.nickname}] Can`t write data. Wrong length "{e}"')
            return {'error': f'Not right length for word or description. You have {e},'
                                                                 f' min 1 - max 135(word) | max 400(description)'}, 404
        except AccessError as e:
            logger.error(f'[{sql_user.nickname}] Can`t write data. Access denied "{e}"')
            return {'error': f'A user with such a token does not have access rights to an example with this id'}, 404
        except Exception as e:
            logger.error(f'[{sql_user.nickname}] Can`t write data "{e}"')
            return {'error': 'Failed to process your word object - check the correctness of the form data'}, 404
        else:
            logger.info(f'[{sql_user.nickname}] WORD IS READY TO BE UPDATED')

        try:
            db_worker.update_data(
                data_type='word',
                data_id=sql_word.word_id,
                new_data=word
            )
            db_worker.update_data(
                data_type='description',
                data_id=sql_word.word_id,
                new_data=description
            )
            sql_word = db_worker.get_word(
                word_id=sql_word.word_id
            )
            returned_data = {
                'word_id': sql_word.word_id,
                'word': sql_word.word,
                'description': sql_word.description,
                'example_id': sql_word.example_id
            }
        except Exception as e:
            logger.error(f'[{sql_user.nickname}] Can`t write data from sql "{e}"')
            return {'error': 'Failed to process your word object - check the correctness of the form data'}, 404
        else:
            logger.info(f'[{sql_user.nickname}] SUCCESS PUT WORD')
            return returned_data, 200

    def delete(self, token, word_id):

        try:
            sql_user = db_worker.get_user_by_api_key(token=token)
        except Exception as e:
            logger.warning(f'[{token}] Can`t find user id "{e}"')
            return {'error': 'Could not find a user with this key, please check your key and try again'}, 404
        else:
            logger.info(f'[{sql_user.nickname}] DELETE WORD')

        try:
            sql_word = db_worker.get_word(word_id=word_id)
            sql_example = db_worker.get_example(example_id=int(sql_word.example_id))
            if not sql_example.user_id == sql_user.user_id:
                raise AccessError(f'Data owner: {sql_example.user_id}, Query owner: {sql_user.user_id}')
        except AccessError as e:
            logger.error(f'[{sql_user.nickname}] Can`t delete data. Access denied "{e}"')
            return {'error': f'A user with such a token does not have access rights to an example with this id'}, 404
        except Exception as e:
            logger.error(f'[{sql_user.nickname}] Can`t delete data "{e}"')
            return {'error': 'Failed to process your word object - check the correctness of the data id'}, 404
        else:
            logger.info(f'[{sql_user.nickname}] WORD IS READY TO BE DELETED')

        try:
            db_worker.delete_data(
                data_type='word',
                data_id=word_id
            )
            sql_word = db_worker.get_word(word_id)
            returned_data = {
                'success': 'Your data has been successfully deleted'
            }
            if sql_word:
                raise RuntimeError('Data was not successfully deleted from sql table')
        except RuntimeError as e:
            logger.error(f'[{sql_user.nickname}] Can`t delete data from sql "{e}"')
            return {'error': 'Data was not successfully deleted from table, problem on our end, please try again'}, 404
        except Exception as e:
            logger.error(f'[{sql_user.nickname}] Can`t delete data from sql "{e}"')
            return {'error': 'Failed to process your word object - check the correctness of the data id'}, 404
        else:
            logger.info(f'[{sql_user.nickname}] SUCCESS DELETE WORD')
            return returned_data, 200


########################################################################################################################
########################################################################################################################
if __name__ == '__main__':
    api.add_resource(Words, '/api/words/<string:token>')
    api.add_resource(Lesson, '/api/lesson/<string:token>')
    api.add_resource(Example, '/api/example/<string:token>/<int:example_id>')
    api.add_resource(Word, '/api/word/<string:token>/<int:word_id>')
    api.init_app(app)
    app.run(
        debug=True,
        port=3000,
        host=HOST
    )

# api to another thread \ subprocess from bot
