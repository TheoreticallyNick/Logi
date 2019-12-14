import unittest
import sys
sys.path.append('../')
from Logi.run.logi_cellular import time_convert

class LogiTest(unittest.TestCase):

    def test_time_convert(self):
        self.assertEqual(time_convert("1232"), (12, 32))

        self.assertEqual(time_convert("0812"), (8, 12))

    

if __name__ == '__main__':
    unittest.main()