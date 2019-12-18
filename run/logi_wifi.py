#!/usr/bin/env python

import sys, os, signal

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
from datetime import datetime, timedelta
import subprocess
from socket import gaierror
from itertools import cycle
import json

schema = 'schema_1_2'

def light_loop(lightObj):
    t = threading.currentThread()
    while getattr(t, "do_run", True):
        lightObj.lightHeart()

def connect_mqtt(client, cloud):
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
            rtc_wake("5", "standby")
            time.sleep(15)
            attempts += 1
            continue

        except connectTimeoutException:
            logging.error('ERR121: MQTT client connection timeout')
            err = err + "E121; "
            rtc_wake("5", "standby")
            time.sleep(15)
            attempts += 1
            continue
            
        if result == True:
            time.sleep(5)
            break
        else:
            logging.error('ERR111: Could not Connect to MQTT Client')
            err = err + "E111; "
            rtc_wake("5", "standby")
            time.sleep(15)
            attempts += 1
            continue

    logging.info('--> Successfully Connected to MQTT Client')
    return cloud, err

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
    
    return myAWSIoTMQTTClient

def rtc_wake(time, mode):
    
    logging.warning('Soft Rebooting...')
    bashCommand = "sudo rtcwake -u -s %s -m %s"%(time, mode)
    process = subprocess.Popen(bashCommand.split(), stdout=subprocess.PIPE)
    output, error = process.communicate()

def time_convert(time_str):

    hr = int(time_str[0:2])
    mn = int(time_str[2:])
    
    return hr, mn

def sleep_calc(time_str):

    hr, mn = time_convert(time_str)

    now = datetime.today()

    if now < now.replace(day=now.day, hour=hr, minute=mn, second=0, microsecond=0):
        nxt = now.replace(day=now.day, hour=hr, minute=mn, second=0, microsecond=0)
    else:
        nxt = now.replace(day=now.day, hour=hr, minute=mn, second=0, microsecond=0) + timedelta(days=1)

    dt = nxt - now
    sec = int(dt.total_seconds())

    return sec

def main():

    ### Set timezone
    os.environ['TZ'] = 'US/Eastern'
    time.tzset()
    timelocal = time.strftime("%Y-%m-%d %H:%M:%S %Z", time.localtime())

    ### Set up the logger
    logi_log = str(time.asctime(time.localtime())) + "logiLog.log"
    logging.basicConfig(filename=logi_log, filemode='w', format='%(asctime)s -- %(levelname)s: %(message)s', level=logging.INFO)
    console = logging.StreamHandler()
    console.setLevel(logging.INFO)
    logging.getLogger('').addHandler(console)

    logging.info('###----------- Logi Wifi Program Start -----------###')

     ### Set sleep schedule
    logging.info('Local Time: %s', timelocal)
    sched = []      # empty schedule list
    n = int(input("Number of publishes per day: "))

    for i in range(0,n):
        w = input("Publish time %i: "%(i+1))
        sched.append(w)     # append time to list       

    print(sched)
    sched_cycle = cycle(sched)

    global wake_time 
    wake_time = sched[1]

    ### Init MQTT Parameters
    logging.info('Initializing MQTT Connection Parameters...')
    mqtt = ConnectMQTTParams()
    myAWSIoTMQTTClient = init_mqtt(mqtt)

    cycleCnt = 1
        
    while True:
        try:
            err = ""
            led_red = CommandLED("P8_8")
            led_red.lightOn()

            ### Connect to MQTT Client
            cloud = None
            cloud, errx = connect_mqtt(myAWSIoTMQTTClient, cloud)
            err = err + errx

            ### Turn on blue light
            led_blu = CommandLED("P8_7")
            led_blu.lightOn()
        
            ### Start connection light heartbeat
            LED_blu_t = threading.Thread(name='light_loop', target=light_loop, args=(led_blu,))
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

            bat_lvl = 95

            wake_time = (next(sched_cycle))

            rssi = "null"
            
            JSONpayload = json.dumps(
                {'id': mqtt.thingName, 'ts': timestamp, 'ts_l': timelocal, 
                'schem': schema, 'wake': wake_time, 'cyc': str(cycleCnt), 'err': err, 
                'rssi': rssi, 'bat': bat_lvl, 'fuel': lev.getPres(), 'temp': mplTemp['c']})
            
            ### Publish to MQTT Broker
            topic = 'logi/devices/%s'%(mqtt.thingName)
            logging.info('Topic: %s', topic)
            logging.info('Published Message: %s', JSONpayload)
            myAWSIoTMQTTClient.publish(topic, JSONpayload, 0)
            cycleCnt = cycleCnt + 1

            ### Turn Off LED and Clean Up GPIO Before Exiting
            LED_blu_t.do_run = False
            LED_blu_t.join()
            led_blu.lightOff()
            led_red.lightOff()
            GPIO.cleanup()
            
            ### Bash Command to Enter Sleep Cycle
            logging.info('Wake up time: %s', wake_time)
            sleep_time = sleep_calc(wake_time)
            logging.info('Sleep time in sec: %s', str(sleep_time))
            time.sleep(sleep_time)
            
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