import sys, os, signal
sys.path.append('/home/debian/Desktop/keys/')
import threading
import json
import time
import psutil
import logging
import subprocess
import ntplib
from time import ctime, sleep
from socket import gaierror
from MQTTconnect import ConnectMQTTParams
from MQTTconnect import CallbackContainer
from AWSIoTPythonSDK.MQTTLib import AWSIoTMQTTClient
from AWSIoTPythonSDK.exception.AWSIoTExceptions import connectTimeoutException
from datetime import datetime, timedelta
from threading import Timer
from itertools import cycle
from ssl import SSLCertVerificationError
from psutil import NoSuchProcess

class LogiMaster:

    def __init__(self):
        self.x = 0

    def init_mqtt(mqtt):
        ### Initializes all parameters and keys for the MQTT broker connection
        myAWSIoTMQTTClient = None

        try:
            myAWSIoTMQTTClient = AWSIoTMQTTClient(mqtt.mqttClientId)
            myAWSIoTMQTTClient.configureEndpoint(mqtt.host, mqtt.port)
            myAWSIoTMQTTClient.configureCredentials(mqtt.rootCAPath, mqtt.privateKeyPath, mqtt.certificatePath)
            myAWSIoTMQTTClient.configureAutoReconnectBackoffTime(1, 32, 20)
            myAWSIoTMQTTClient.configureConnectDisconnectTimeout(10)  # 10 sec
            myAWSIoTMQTTClient.configureMQTTOperationTimeout(5)  # 5 sec
            myCallbackContainer = CallbackContainer(myAWSIoTMQTTClient)
            logging.info('--> Successfully Initialized!')

        except:
            logging.error('ERR113: Error Initializing MQTT Connection Parameters')
            os._exit(1)
        
        return myAWSIoTMQTTClient, myCallbackContainer

    def main():

        print("------- Starting Logi Master Program -------")
        err = ''

        mqtt = ConnectMQTTParams()
        myAWSIoTMQTTClient, myCallbackContainer = init_mqtt(mqtt)

        ### Connect to MQTT Client
        logging.info('Connecting to MQTT...')
        mqtt_result = myAWSIoTMQTTClient.connect()

        if mqtt_result == False: 
            logging.error('ERR111: Could not Connect to MQTT Client')
            err = err + "E111; "
        else: 
            logging.info('--> Successfully Connected to MQTT Client')

        time.sleep(3)

        while True:
            ### Subscribe to MQTT Topics
            myAWSIoTMQTTClient.subscribe("logi/devices/#", 0, myCallbackContainer.messagePrint)
            time.sleep(360)
    

if __name__=="__main__":
    logi = LogiMaster()
    logi.main()