import unittest
import sys, os        
import ntplib
from time import ctime
from datetime import datetime, timezone
sys.path.append('/home/debian/Desktop/Logi/run')
from logi_cellular import *

class LogiTest(unittest.TestCase):

    def test_time_convert(self):
        self.assertEqual(time_convert('1232'), (12, 32))
        self.assertEqual(time_convert('0812'), (8, 12))

    def test_get_ntp(self):

        c = ntplib.NTPClient()
        # Provide the respective ntp server ip in below function
        response = c.request('0.debian.pool.ntp.org', version=3)
        response.offset 
        print(response)
        ntpDate = ctime(response.tx_time)
        print(ntpDate)

if __name__ == '__main__':
    unittest.main()