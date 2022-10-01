import unittest
import pathlib
import os
import datetime

from app.handlers import statistic


########################################################################################################################
class HandlersTestCase(unittest.TestCase):
    """
    Tests for handler sync func
    """

    def test_build_graph(self):
        """
        Test is the func test_build_graph returns correct file path
        """
        path = '../../../temporary/'
        for i in pathlib.Path(path).rglob('*'):
            os.remove(i)
        actual = os.path.isfile(statistic.build_graph(
            user_id='test',
            days=['M', 'T', 'W'],
            total=[100, 1000, 0],
            mistakes=[98, 1, 0],
            first_try=[2, 9999, 0],
            path=path
        ))
        expected = True
        self.assertEqual(expected, actual)

    def test_get_seven_day(self):
        """
        Test is the func get_seven_day returns correct today date
        """
        expected = statistic.get_seven_day()[-1]
        actual = ['Mo', 'Tu', 'We', 'Th', 'Fr', 'Sr', 'Su'][datetime.datetime.today().weekday()]
        self.assertEqual(expected, actual)


########################################################################################################################
if __name__ == "__main__":    # coverage run -m unittest module | coverage run -m unittest module
    unittest.main()
