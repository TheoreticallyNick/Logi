import sys
sys.path.append('../')
from run.logi_connect import LogiConnect
import unittest

class LogiConnectTest(unittest.TestCase):

    def setUp(self):
        self.logi = LogiConnect()
        self.logi.create_cloud()

    def test_get_rssi(self):
        self.assertTrue(type(self.logi.get_rssi()) is float)
    
    #def tearDownClass()
        #self.logi.cell_disconnect()

if __name__ == '__main__':
    unittest.main()