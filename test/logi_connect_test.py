from ..run.logi_connect import LogiConnect
import unittest

class LogiConnectTest(unittest.TestCase):

    def setUp(self):
        self.logi = LogiConnect()

    def test_rssi(self):
        print(self.logi.get_rssi())


if __name__ == '__main__':
    unittest.main()