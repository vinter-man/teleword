import unittest
import datetime
import os
import pathlib

from app import db_worker
from config import config


########################################################################################################################
class DbWorkerTestCase(unittest.TestCase):
    """
    Tests for 'db_worker.py'.
    """

    def test_tables(self):
        """
        Checking if there are tables in the database after module import
        """
        actual_tables_data = db_worker.engine.execute('SHOW TABLES;')
        expected_table_data = [('apikeys',), ('examples',), ('statistics',), ('users',), ('words',)]
        self.assertEqual(expected_table_data, list(actual_tables_data))

    def test_is_user(self):
        """
        Examination of is_user func
        """
        actual = db_worker.is_user(telegram_id=config.ADMIN_ID_TG)
        self.assertTrue(actual)

    def test_get_user(self):
        """
        Does the get_user function return a full Python object to work with
        """
        actual_obj = db_worker.get_user(tg_id=str(config.ADMIN_ID_TG))
        self.assertEqual(str(config.ADMIN_ID_TG), actual_obj.tg_id)

    def test_add_user(self):
        """
        Correctness of adding new user in db process
        """
        today = str(datetime.date.today())
        db_worker.engine.execute(
            """
            DELETE FROM users 
            WHERE nickname = 'test'
            AND lang_code = 'ru'
            AND tg_id='TEST00000'
            AND shock_mode = 0
            AND points = 0
            AND is_blacklisted = 0
            AND is_bot = 0
            AND creation_time = '{0}'
            AND last_use_time = '{0}'
            AND current_use_time = '{0}'
            """.format(today))
        db_worker.add_user(
            tg_id='TEST00000',
            nickname='test',
            lang_code='ru',
            shock_mode=0,
            points=0,
            is_blacklisted=False,
            is_bot=False,
            creation_time=today,
            last_use_time=today,
            current_use_time=today
        )
        actual_user_data = db_worker.engine.execute(
            """
            SELECT * FROM users 
            WHERE nickname = 'test'
            AND lang_code = 'ru'
            AND tg_id='TEST00000'
            AND shock_mode = 0
            AND points = 0
            AND is_blacklisted = 0
            AND is_bot = 0
            AND creation_time = '{0}'
            AND last_use_time = '{0}'
            AND current_use_time = '{0}'
            """.format(today))
        self.assertIn(('TEST00000', 'test', 'ru', 0, 0, 0, 0, today, today, today), [i[1:] for i in actual_user_data])

    def test_users_bl_list(self):
        """
        Test is the blacklist returned correctly
        """
        actual_bl = db_worker.users_bl_list()
        expected_bl = list(db_worker.engine.execute('SELECT * FROM users WHERE is_blacklisted=1'))
        self.assertEqual(expected_bl, actual_bl)

    def test_change_user_last_using_increasing(self):
        """
        Test is the shock mode status increasing works correctly
        """
        today = str(datetime.date.today())
        db_worker.engine.execute(
            """
            DELETE FROM users WHERE tg_id='TEST00001'
            """.format(today, today))
        db_worker.add_user(
            tg_id='TEST00001',
            nickname='test',
            lang_code='ru',
            shock_mode=0,
            points=0,
            is_blacklisted=False,
            is_bot=False,
            creation_time=today,
            last_use_time='2022-09-29',
            current_use_time='2022-09-30'
        )
        db_worker.change_user_last_using(user_tg_id='TEST00001')
        actual = db_worker.get_user(tg_id='TEST00001').shock_mode
        expected = 1
        self.assertEqual(expected, actual)

    def test_change_user_last_using_reset(self):
        """
        Test is the shock mode status reset works correctly
        """
        today = str(datetime.date.today())
        db_worker.engine.execute(
            """
            DELETE FROM users WHERE tg_id='TEST00002'
            """.format(today, today))
        db_worker.add_user(
            tg_id='TEST00002',
            nickname='test',
            lang_code='ru',
            shock_mode=0,
            points=0,
            is_blacklisted=False,
            is_bot=False,
            creation_time=today,
            last_use_time='2022-09-28',
            current_use_time='2022-09-30'
        )
        db_worker.change_user_last_using(user_tg_id='TEST00002')
        actual = db_worker.get_user(tg_id='TEST00002').shock_mode
        expected = 0
        self.assertEqual(expected, actual)

    def test_change_user_bl_status(self):
        """
        Test is the black list status changing works correctly
        """
        actual_user_status_before = db_worker.get_user(tg_id=config.ADMIN_ID_TG).is_blacklisted
        expected_user_status_before = False
        db_worker.change_user_bl_status(user_tg_id=config.ADMIN_ID_TG, change_for=True)
        actual_user_status_after = db_worker.get_user(tg_id=config.ADMIN_ID_TG).is_blacklisted
        expected_user_status_after = True
        db_worker.change_user_bl_status(user_tg_id=config.ADMIN_ID_TG, change_for=False)
        self.assertEqual(
            (expected_user_status_before, expected_user_status_after),
            (actual_user_status_before, actual_user_status_after)
        )

    def test_add_example(self):
        """
        Correctness of adding new example in db process
        """
        user_id = db_worker.get_user(tg_id=config.ADMIN_ID_TG).user_id
        db_worker.add_example(
            example_text='testexample',
            user_tg_id=config.ADMIN_ID_TG
        )
        actual = db_worker.engine.execute(
            """
            SELECT * FROM examples 
            WHERE example = 'testexample'
            AND user_id = {}
            """.format(user_id))
        expected = ('testexample', user_id)
        self.assertIn(expected, [i[1:] for i in actual])

    def test_add_word(self):
        """
        Correctness of adding new word in db process
        """
        db_worker.engine.execute(
            """
            DELETE FROM words 
            WHERE word = 'testword'
            AND description  = 'testdescription'
            """)
        db_worker.pending_rollback(username='test')
        test_example = db_worker.add_example(
            example_text='testexample',
            user_tg_id=config.ADMIN_ID_TG
        )
        db_worker.add_word(
            word='testword',
            description='testdescription',
            category='testcategory',
            rating=0,
            example=test_example
        )
        actual = db_worker.engine.execute(
            """
            SELECT * FROM words 
            WHERE word = 'testword'
            AND description  = 'testdescription'
            AND example_id = {}
            """.format(test_example.ex_id))
        expected = ('testword', 'testdescription', 'testcategory', 0)
        self.assertIn(expected, [i[1:-1] for i in actual])

    def test_get_word(self):
        """
        Test is the get sql word obj returns correctness python obj
        """
        test_example = db_worker.add_example(
            example_text='testexample',
            user_tg_id=config.ADMIN_ID_TG
        )
        test_word = db_worker.add_word(
            word='testword',
            description='testdescription',
            category='testcategory',
            rating=0,
            example=test_example
        )
        expected = test_word
        actual = db_worker.get_word(word_id=test_word.word_id)
        self.assertEqual(expected, actual)

    def test_change_rating(self):
        """
        Test is the word rating changes correctly
        """
        test_example = db_worker.add_example(
            example_text='testexample',
            user_tg_id=config.ADMIN_ID_TG
        )
        test_word = db_worker.add_word(
            word='testword',
            description='testdescription',
            category='testcategory',
            rating=0,
            example=test_example
        )
        expected = 100
        db_worker.change_rating(word_id=test_word.word_id, new_rating=expected)
        actual = db_worker.get_word(word_id=test_word.word_id).rating
        self.assertEqual(expected, actual)

    def test_add_or_change_day_stat_points(self):
        """
        Test is the func changes point count correctly
        """
        test_user = db_worker.get_user(tg_id=config.ADMIN_ID_TG)
        expected = test_user.points + 1
        db_worker.add_or_change_day_stat(
            tg_id=test_user.tg_id,
            first_try=0,
            mistakes=0,
            points=1
        )
        actual = test_user.points
        self.assertEqual(expected, actual)

    def test_get_words_data(self):
        """
        Test is the word data returns correctly
        """
        sql_query = db_worker.engine.execute(
            " SELECT "
            " examples.user_id, words.word, words.description, examples.example, words.category, words.rating, "
            " words.word_id "
            " FROM users"
            " LEFT JOIN examples ON examples.user_id = users.user_id"
            " LEFT JOIN words ON words.example_id = examples.ex_id"
            " WHERE users.tg_id = '{}'".format(config.ADMIN_ID_TG)
        )
        expected = [
            {
                'tg_id': i.user_id,
                'word': i.word,
                'description': i.description,
                'example': i.example,
                'category': i.category,
                'rating': i.rating,
                'word_id': i.word_id,
                'is_main': False
            }
            for i in sql_query
        ]
        actual = db_worker.get_words_data(user_tg_id=config.ADMIN_ID_TG)
        self.assertEqual(expected, actual)

    def test_get_lesson_data(self):
        """
        Test is the lesson contains correct number of tasks
        """
        expected = 15
        actual = len(db_worker.get_lesson_data(tg_id=config.ADMIN_ID_TG))
        self.assertEqual(expected, actual)

    def test_word_count(self):
        """
        Test is the func word_count returns correct word count after adding new word
        """
        db_worker.engine.execute(
            """
            DELETE FROM words 
            WHERE word = 'testword2'
            AND description  = 'testdescription2'
            """)
        db_worker.pending_rollback(username='test')
        expected = db_worker.word_count(user_tg_id=config.ADMIN_ID_TG) + 1
        test_example = db_worker.add_example(
            example_text='testexample',
            user_tg_id=config.ADMIN_ID_TG
        )
        db_worker.add_word(
            word='testword2',
            description='testdescription2',
            category='testcategory2',
            rating=0,
            example=test_example
        )
        actual = db_worker.word_count(user_tg_id=config.ADMIN_ID_TG)
        self.assertEqual(expected, actual)

    def test_get_user_stat_len(self):
        """
        Test is the func get_user_stat returns list with correct len
        """
        expected = 7
        stat_data = db_worker.get_user_stat(user_tg_id=config.ADMIN_ID_TG, limit=expected)
        actual = len(list(stat_data))
        self.assertEqual(expected, actual)

    def test_get_user_stat_type(self):
        """
        Test is the func get_user_stat returns list with correct python classes
        """
        stat_data = db_worker.get_user_stat(user_tg_id=config.ADMIN_ID_TG, limit=1)
        expected = db_worker.UsersStatistics
        actual = type(stat_data[0])
        self.assertEqual(expected, actual)

    def test_build_total_mistakes_firsttry_data_for_graph(self):
        """
        Test is the func get_user_stat returns lists with correct len as value of dict
        """
        expected_len = 7
        stat_data = db_worker.build_total_mistakes_firsttry_data_for_graph(
            user_sql_logs=db_worker.get_user_stat(
                config.ADMIN_ID_TG, limit=expected_len
            ),
            future_length=expected_len
        )
        expected = [expected_len] * 3
        actual = [len(i) for i in stat_data.values()]
        self.assertEqual(expected, actual)

    def test_create_file_with_user_words(self):
        """
        Test is the func create_file_with_user_words returns correct file path
        """
        path = '../../../temporary'
        for i in pathlib.Path(path).rglob('*'):
            os.remove(i)
        actual = os.path.isfile(db_worker.create_file_with_user_words(
            user_tg_id=str(config.ADMIN_ID_TG),
            file_path=path,
            file_type='json',
            sql_filter_key='default',
            sql_sort_key='default')
        )
        expected = True
        self.assertEqual(expected, actual)

    def test_get_user_example_id(self):
        """
        Test is the func get_user_example returns correct python type by id
        """
        expected = db_worker.add_example(
            example_text='testexample',
            user_tg_id=config.ADMIN_ID_TG
        )
        actual = db_worker.get_user_example(
            user=db_worker.get_user(tg_id=config.ADMIN_ID_TG),
            example_id=expected.ex_id,
        )
        self.assertEqual(expected, actual)

    def test_get_user_example_text(self):
        """
        Test is the func get_user_example returns correct python type by example text
        """
        expected = db_worker.add_example(
            example_text='testexample',
            user_tg_id=config.ADMIN_ID_TG
        )
        actual = db_worker.get_user_example(
            user=db_worker.get_user(tg_id=config.ADMIN_ID_TG),
            example=expected.example,
        )
        self.assertEqual(expected, actual)

    def test_get_user_example_none(self):
        """
        Test is the func get_user_example returns correct python type by negative data
        """
        expected = None
        actual = db_worker.get_user_example(
            user=db_worker.get_user(tg_id=config.ADMIN_ID_TG),
            example_id=-1,
        )
        self.assertEqual(expected, actual)

    def test_get_example(self):
        """
        Does the get_example function return a Python object to work with it
        """
        expected = db_worker.add_example(
            example_text='testexample',
            user_tg_id=config.ADMIN_ID_TG
        )
        actual = db_worker.get_example(
            example_id=expected.ex_id
        )
        self.assertEqual(expected, actual)

    def test_get_user_word_id(self):
        """
        Test is the func get_user_word returns correct python type by word id
        """
        test_example = db_worker.add_example(
            example_text='testexample',
            user_tg_id=config.ADMIN_ID_TG
        )
        expected = db_worker.add_word(
            word='testword2',
            description='testdescription2',
            category='testcategory2',
            rating=0,
            example=test_example
        )
        actual = db_worker.get_user_word(
            user=db_worker.get_user(tg_id=config.ADMIN_ID_TG),
            word_id=expected.word_id
        )
        self.assertEqual(expected, actual)

    def test_get_user_word_word(self):
        """
        Test is the func get_user_word returns correct python type by word
        """
        test_example = db_worker.add_example(
            example_text='testexample',
            user_tg_id=config.ADMIN_ID_TG
        )
        expected = db_worker.add_word(
            word='testword2',
            description='testdescription2',
            category='testcategory2',
            rating=0,
            example=test_example
        )
        actual = db_worker.get_user_word(
            user=db_worker.get_user(tg_id=config.ADMIN_ID_TG),
            word=expected.word
        )
        self.assertEqual(expected, actual)

    def test_get_user_word_description(self):
        """
        Test is the func get_user_word returns correct python type by description
        """
        test_example = db_worker.add_example(
            example_text='testexample',
            user_tg_id=config.ADMIN_ID_TG
        )
        expected = db_worker.add_word(
            word='testword2',
            description='testdescription2',
            category='testcategory2',
            rating=0,
            example=test_example
        )
        actual = db_worker.get_user_word(
            user=db_worker.get_user(tg_id=config.ADMIN_ID_TG),
            description=expected.description
        )
        self.assertEqual(expected, actual)

    def test_get_word_category(self):
        """
        Test is the func get_word_category returns string word category by the available parameters
        """
        expected = 'Noun'
        actual = db_worker.get_word_category(
            word='test',
            default='-',
            url=config.URL_OXF
        )
        self.assertEqual(expected, actual)

    def test_update_data_word(self):
        """
        Test is the func update_data success updates word data
        """
        db_worker.engine.execute(
            """
            DELETE FROM words 
            WHERE word = 'testword3'
            AND description  = 'testdescription3'
            OR word = 'testword3_1'
            AND description  = 'testdescription3'
            """)
        test_example = db_worker.add_example(
            example_text='testexample',
            user_tg_id=config.ADMIN_ID_TG
        )
        test_word = db_worker.add_word(
            word='testword3',
            description='testdescription3',
            category='testcategory3',
            rating=0,
            example=test_example
        )
        expected = 'testword3_1'
        db_worker.update_data(
            data_type='word',
            data_id=test_word.word_id,
            new_data=expected
        )
        actual = db_worker.get_word(test_word.word_id).word
        self.assertEqual(expected, actual)

    def test_update_data_description(self):
        """
        Test is the func update_data success updates word description
        """
        db_worker.engine.execute(
            """
            DELETE FROM words 
            WHERE word = 'testword3'
            AND description  = 'testdescription3'
            OR word = 'testword3'
            AND description  = 'testdescription3_1'
            """)
        test_example = db_worker.add_example(
            example_text='testexample',
            user_tg_id=config.ADMIN_ID_TG
        )
        test_word = db_worker.add_word(
            word='testword3',
            description='testdescription3',
            category='testcategory3',
            rating=0,
            example=test_example
        )
        expected = 'testdescription3_1'
        db_worker.update_data(
            data_type='description',
            data_id=test_word.word_id,
            new_data=expected
        )
        actual = db_worker.get_word(test_word.word_id).description
        self.assertEqual(expected, actual)

    def test_delete_data_word(self):
        """
        Test correctness of word deleting
        """
        db_worker.engine.execute(
            """
            DELETE FROM words 
            WHERE word = 'testword4'
            AND description  = 'testdescription4'
            """)
        test_example = db_worker.add_example(
            example_text='testexample',
            user_tg_id=config.ADMIN_ID_TG
        )
        test_word = db_worker.add_word(
            word='testword4',
            description='testdescription4',
            category='testcategory4',
            rating=0,
            example=test_example
        )
        expected = None
        db_worker.delete_data(
            data_type='word',
            data_id=test_word.word_id,
        )
        actual = db_worker.get_word(test_word.word_id)
        self.assertEqual(expected, actual)

    def test_delete_data_description(self):
        """
        Test correctness of word deleting
        """
        db_worker.engine.execute(
            """
            DELETE FROM words 
            WHERE word = 'testword4'
            AND description  = 'testdescription4'
            """)
        test_example = db_worker.add_example(
            example_text='testexample',
            user_tg_id=config.ADMIN_ID_TG
        )
        test_word = db_worker.add_word(
            word='testword4',
            description='testdescription4',
            category='testcategory4',
            rating=0,
            example=test_example
        )
        expected = None
        db_worker.delete_data(
            data_type='description',
            data_id=test_word.word_id,
        )
        actual = db_worker.get_word(test_word.word_id)
        self.assertEqual(expected, actual)

    def test_delete_data_example(self):
        """
        Test correctness of word deleting
        """
        db_worker.engine.execute(
            """
            DELETE FROM words 
            WHERE word = 'testword4'
            AND description  = 'testdescription4'
            """)
        test_example = db_worker.add_example(
            example_text='testexample4',
            user_tg_id=config.ADMIN_ID_TG
        )
        expected = None
        db_worker.delete_data(
            data_type='example',
            data_id=test_example.ex_id,
        )
        actual = db_worker.get_example(example_id=test_example.ex_id)
        self.assertEqual(expected, actual)

    def test_generate_is_api_keys(self):
        """
        Test is apikey adding
        """
        admin = db_worker.get_user(tg_id=config.ADMIN_ID_TG)
        expected = bool(len(list(db_worker.engine.execute(
            'SELECT * FROM apikeys WHERE user_id = {}'.format(admin.user_id)))))
        actual = db_worker.is_api_keys(user=admin)
        self.assertEqual(expected, actual)

    def test_get_user_api_key(self):
        """
        Test is func get_user_api_key returns correct key
        """
        admin = db_worker.get_user(tg_id=config.ADMIN_ID_TG)
        expected = list(db_worker.engine.execute(
            'SELECT * FROM apikeys WHERE user_id = {}'.format(admin.user_id)))[0][1]
        actual = db_worker.get_user_api_key(user=admin)
        self.assertEqual(expected, actual)

    def test_get_user_by_api_key(self):
        """
        Test is func get_user_by_api_key returns correct python obj
        """
        expected = db_worker.get_user(tg_id=config.ADMIN_ID_TG)
        actual = db_worker.get_user_by_api_key(token=db_worker.get_user_api_key(user=expected))
        self.assertEqual(expected, actual)


########################################################################################################################
if __name__ == "__main__":    # coverage run -m unittest module | coverage run -m unittest module
    unittest.main()
