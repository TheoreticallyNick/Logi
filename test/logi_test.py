import unittest
import sys, os 
sys.path.append("C:\\Users\\Windows_Admin\\Dropbox\\Greater Lakes Engineering\\Clients\\Internal Projects\\IoT\\Logi\\Software\\Logi\\run")       
import ntplib
from time import ctime
from datetime import datetime, timezone
from logi_cellular import LogiConnect

class LogiTest(unittest.TestCase):

    def test_time_str(self):
        self.assertEqual(time_split('1232'), (12, 32))
        self.assertEqual(time_split('0812'), (8, 12))

    def test_time_now_str(self):
        self.assertEqual(time_now_str(sched)) 

if __name__ == '__main__':
    unittest.main()