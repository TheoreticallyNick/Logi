#!/bin/bash
import sys, os, signal
sys.path.append('/home/debian/Desktop/Logi/controls/')
sys.path.append('/home/debian/Desktop/keys/')
import threading
import json
import time
from time import ctime, sleep
import logging
import subprocess
from socket import gaierror
import psutil
from serial.serialutil import SerialException
import Adafruit_BBIO.GPIO as GPIO
import Adafruit_BBIO.ADC as ADC
from Hologram.Network import Network, Cellular
from Hologram.HologramCloud import HologramCloud
from Hologram.CustomCloud import CustomCloud
from Exceptions.HologramError import NetworkError, PPPError, SerialError, HologramError
from MQTTconnect import ConnectMQTTParams
from MQTTconnect import CallbackContainer
from AWSIoTPythonSDK.MQTTLib import AWSIoTMQTTClient
from AWSIoTPythonSDK.exception.AWSIoTExceptions import *
from LED import CommandLED
from AD8 import Thermocouple
from PX3 import Pressure
from MPL import MPL3115A2
from DS1318 import FluidLevel
from datetime import datetime, timedelta
from threading import Timer
from itertools import cycle
from ssl import SSLCertVerificationError
from psutil import NoSuchProcess
import ntplib
from PWR import Battery
from logi_cellular import LogiConnect

### TODO:
#       - Put together an array of the connection function
#       - Look into using Docker to create the right virtual machine to run this on 
#       - Determine appropriate tunnel time window
    
logi = LogiConnect()

### Set up the logger
logi.set_logger()

### Start the program
logging.info('###---------- Logi Cellular v1.1.4 Program Start ----------###')

myAWSIoTMQTTClient, callBackContainer = logi.init_mqtt(logi.mqtt)

### Schema Version
logging.info('MQTT Schema: %s', logi.schema) 

### Connection Cycle
logging.info('Initial connection and calibration...')

### Calibrate system clock
rolex = logi.time_fetch()
logi.set_time(rolex)

### Set sleep schedule
sched_cycle, wake_time = logi.set_schedule()

### Init Board I/O
lev, mpl, bat = logi.set_board_io()

### Publish Program Loop
while True:

    ### Start cycle
    logging.info('###---------- Starting Cycle Number: %i ----------###', logi.cycle_cnt)
    led_red = CommandLED('P8_7')
    led_red.lightOn()

    ### Start Connection Process            
    logi.mqtt_connect(myAWSIoTMQTTClient)

    ### Record the RSSI
    try: 
        rssi = cloud.network.signal_strength
    except:
        logging.error('ERR117: Error getting RSSI values')
        rssi = '99,99'
        logi.err = logi.err + 'E117; '

    ### Subscribe to MQTT Topics
    #mstr_topic = 'logi/master/%s'%(logi.mqtt.thingName)
    #logi.myAWSIoTMQTTClient.subscribe(mstr_topic, 0, logi.custom_callback)

    ### Timestamp 
    timestamp = time.time()
    timelocal = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime())

    ### Get Temperature Data from MPL
    try:
        mpl.control_alt_config()
        mpl.data_config()
        mplTemp = mpl.read_alt_temp()
    except:
        logging.error('ERR119: I2C bus error')
        logi.err = logi.err + 'E119; '
        mplTemp = {'a' : 999, 'c' : 999, 'f' : 999}

    ### Next Wake Up Time
    wake_time = (next(sched_cycle))

    ### Set the MQTT Message Payload
    JSONpayload = json.dumps(
    {'id': logi.mqtt.thingName, 'ts': timestamp, 'ts_l': timelocal, 
    'schem': logi.schema, 'ver': logi.version, 'wake': wake_time, 'cyc': str(logi.cycle_cnt), 'err': logi.err, 
    'rssi': rssi, 'bat': bat.getVoltage(), 'lvl': lev.getLev(), 'temp': mplTemp['c']})

    ### Publish to MQTT Broker
    att = 1
    while True:
        try:
            logi.publish_mqtt(JSONpayload, myAWSIoTMQTTClient)
        except:
            logging.error('ERR141: Unable to Publish to MQTT, publish cycle skipped')
            logi.err = logi.err + 'ERR141; '
            time.sleep(30)
            continue
        finally:
            logi.err = ''
            break

    logi.cycle_cnt = logi.cycle_cnt + 1

    ### Subscribed time window
    time.sleep(10)

    ### Disconnect from MQTT
    myAWSIoTMQTTClient.disconnect()

    ### Cycle LED's to OFF
    led_red.lightOff()
    GPIO.cleanup()

    ### Bash Command to Enter Sleep Cycle
    logging.info('Wake up time: %s', wake_time)
    sleep_time = logi.sleep_calc(wake_time)
    logging.info('Next Pub Time in sec: %s', str(sleep_time))
    time.sleep(sleep_time)
