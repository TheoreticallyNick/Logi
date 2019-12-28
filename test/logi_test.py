import unittest
import sys, os 
sys.path.append("C:\\Users\\Windows_Admin\\Dropbox\\Greater Lakes Engineering\\Clients\\Internal Projects\\IoT\\Logi\\Software\\Logi\\run")       
import ntplib
from time import ctime
from datetime import datetime, timezone
from logi_cellular import time_now_str, time_convert

class LogiTest(unittest.TestCase):

    def test_time_convert(self):
        self.assertEqual(time_convert('1232'), (12, 32))
        self.assertEqual(time_convert('0812'), (8, 12))

    def test_order_sched(self):
        sched = ['1200', '0900']
        self.assertEqual(order_sched()) 

if __name__ == '__main__':
    unittest.main()