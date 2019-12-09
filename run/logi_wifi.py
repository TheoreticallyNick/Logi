#!/usr/bin/env python

import sys, os, signal

sys.path.append('/home/debian/Desktop/Logi/controls/')
activate_this_file = "/home/debian/Desktop/Logi/bin/activate_this.py"
exec(compile(open(activate_this_file, "rb").read(), activate_this_file, 'exec'), dict(__file__=activate_this_file))

sys.path.append('/home/debian/Desktop/Logi/controls/')
sys.path.append('/home/debian/Desktop/keys/')
from MQTTconnect import ConnectMQTTParams
from MQTTconnect import CallbackContainer
from AWSIoTPythonSDK.MQTTLib import AWSIoTMQTTClient
from AWSIoTPythonSDK.exception.AWSIoTExceptions import *
from LED import CommandLED
from AD8 import Thermocouple
from PX3 import Pressure
from MPL import MPL3115A2
from socket import gaierror
from DS1318 import FluidLevel
import Adafruit_BBIO.GPIO as GPIO
import Adafruit_BBIO.ADC as ADC
import threading
import time
import logging
from datetime import datetime
import subprocess
from socket import gaierror

def lightLoop(lightObj):
    t = threading.currentThread()
    while getattr(t, "do_run", True):
        lightObj.lightHeart()

def connectMQTT(client, cloud):
    ### Redundancy for Connecting to MQTT Client ###
    logging.info('Connecting to MQTT...')
    attempts = 1
    err = ""

    while attempts <= 4:
        logging.info('- MQTT Client Connection Attempt %i -', attempts)

        if attempts == 4:
            logging.critical('FATAL ERROR: %s', err)
            logging.critical('3 attempts made to connect to MQTT Client')
            os._exit(1) 

        try:
            result = client.connect()

        except gaierror:
            logging.error('ERR109: Temporary failure in DNS server name resolution')
            err = err + "E109; "
            rtcWake("5", "standby")
            time.sleep(15)
            attempts += 1
            continue

        except connectTimeoutException:
            logging.error('ERR121: MQTT client connection timeout')
            err = err + "E121; "
            rtcWake("5", "standby")
            time.sleep(15)
            attempts += 1
            continue
            
        if result == True:
            time.sleep(5)
            break
        else:
            logging.error('ERR111: Could not Connect to MQTT Client')
            err = err + "E111; "
            rtcWake("5", "standby")
            time.sleep(15)
            attempts += 1
            continue

    logging.info('--> Successfully Connected to MQTT Client')
    return cloud, err

def initMQTTClient(mqtt):
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
    
    return myAWSIoTMQTTClient

def rtcWake(time, mode):
    
    logging.warning('Soft Rebooting...')
    bashCommand = "sudo rtcwake -u -s %s -m %s"%(time, mode)
    process = subprocess.Popen(bashCommand.split(), stdout=subprocess.PIPE)
    output, error = process.communicate()

def main():

    ### Set up the logger
    logging.basicConfig(filename='logi_runtime.log', filemode='w', format='%(asctime)s -- %(levelname)s: %(message)s', level=logging.INFO)
    console = logging.StreamHandler()
    console.setLevel(logging.INFO)
    logging.getLogger('').addHandler(console)

    logging.info('###----------- Logi Wifi Program Start -----------###')

    ### Set timezone
    tz = 'EST'
    os.environ['TZ'] = 'US/Eastern'
    logging.info('Setting timezone to %s...', tz)
    time.tzset() 
    timelocal = time.strftime("%Y-%m-%d %H:%M:%S %Z", time.localtime())

    ### Set sleep cycle
    logging.info('Local Time: %s', timelocal)
    sleepTime = (input("Sleep Time in Seconds: "))
    logging.info('Sleep cycle set to %s seconds', sleepTime)

    ### Init MQTT Parameters
    logging.info('Initializing MQTT Connection Parameters...')
    mqtt = ConnectMQTTParams()
    myAWSIoTMQTTClient = initMQTTClient(mqtt)

    cycleCnt = 1
        
    while True:
        try:
            err = ""
            led_red = CommandLED("P8_8")
            led_red.lightOn()

            ### Connect to MQTT Client
            cloud = None
            cloud, errx = connectMQTT(myAWSIoTMQTTClient, cloud)
            err = err + errx

            ### Turn on blue light
            led_blu = CommandLED("P8_7")
            led_blu.lightOn()
        
            ### Start connection light heartbeat
            LED_blu_t = threading.Thread(name='lightLoop', target=lightLoop, args=(led_blu,))
            LED_blu_t.start()

            ### Subscribe to MQTT Topics
            #myAWSIoTMQTTClient.subscribe("topic/devices/cast", 0, myCallbackContainer.messagePrint)

            ### Init Board I/O
            logging.info('Initialing Board I/O...')
            try: 
                ADC.setup()
                lev     = Pressure("P9_39")
                mpl     = MPL3115A2()
                logging.info('--> Successfully Initialized I/O')
            except:
                logging.error('ERR115: Error initializing board I/O')
                err = err + "E115; "

            ### Pull the Timestamp    
            timestamp = time.time()
            timelocal = time.strftime("%Y-%m-%d %H:%M:%S %Z", time.localtime())
            
            ### Pull the Temperature Value from MPL
            try:
                mpl.control_alt_config()
                mpl.data_config()
                mplTemp = mpl.read_alt_temp()
            except:
                logging.error('ERR119: I2C bus error')
                err = err + "E119; "
                mplTemp = {'a' : 999, 'c' : 999, 'f' : 999}

            JSONpayload = '{"id": "%s", "ts": "%s", "ts_l": "%s", "schem": "1.2", "slp": "%s", "cyc": "%s", "err": "%s", "rssi": "wifi", "bat": "bat", "lvl": %.2f, "temp": %.2f}'%(mqtt.thingName, timestamp, timelocal, sleepTime, str(cycleCnt), err, lev.getPres(), mplTemp['c'])
            
            myAWSIoTMQTTClient.publish("topic/devices/data", JSONpayload, 0)
            topic = 'logi/devices/%s'%(mqtt.thingName)
            logging.info('Topic: %s', topic)
            logging.info('Published Message: %s', JSONpayload)            
            
            cycleCnt = cycleCnt + 1

            ### Turn Off LED and Clean Up GPIO Before Exiting
            LED_blu_t.do_run = False
            LED_blu_t.join()
            led_blu.lightOff()
            led_red.lightOff()
            GPIO.cleanup()
            
            ### Bash Command to Enter Sleep Cycle
            logging.info('Going to Sleep for %s seconds', str(sleepTime))
            rtcWake(str(sleepTime), "standby")
            time.sleep(20)
            
        except KeyboardInterrupt:
            pass
            
    ### Turn Off LED and Clean Up GPIO Before Exiting
    LED_blu_t.do_run = False
    LED_blu_t.join()
    led_blu.lightOff()
    led_red.lightOff()
    
    GPIO.cleanup()
    print("\n Program Terminated")

    os._exit(1)

if __name__=="__main__":
    main()