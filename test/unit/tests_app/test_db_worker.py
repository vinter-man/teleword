# All what we want for test file:
import unittest
import datetime

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
        self.assertEqual(list(actual_tables_data), expected_table_data)

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
        self.assertEqual(actual_obj.tg_id, str(config.ADMIN_ID_TG))

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
        self.assertEqual(actual_bl, expected_bl)

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
            (actual_user_status_before, actual_user_status_after),
            (expected_user_status_before, expected_user_status_after)
        )



    # def test_first_last_midle_name(self):    # if name starts 'test_...' - autostart
    #     """Are names form 'Wolfgang Amadeus Mozart' working well?"""
    #     formated_name = get_formatted_name('wolfgang', 'mozart', 'amadeus')
    #     self.assertEqual(formated_name, 'Wolfgang Amadeus Mozart')
    #     # assersEqual(f, v) f==v
    #     # assertNotEqual(f, v) f!=v
    #     # assertTrue(x) x == True
    #     # assertFalse(x) x == False
    #     # assertIn(x, list) x in list == True
    #     # assertNotIn(x, list) x not in list == True


########################################################################################################################
if __name__ == "__main__":    # coverage run -m unittest module | coverage run -m unittest module
    unittest.main()