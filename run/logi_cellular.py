#!/usr/bin/env python

import sys, os, signal

activate_this_file = "/home/debian/Desktop/Logi/bin/activate_this.py"
exec(compile(open(activate_this_file, "rb").read(), activate_this_file, 'exec'), dict(__file__=activate_this_file))

sys.path.append('/home/debian/Desktop/Logi/controls/')
sys.path.append('/home/debian/Desktop/keys/')

import threading
import json
import time
import logging
import subprocess
from socket import gaierror
import psutil
from serial import SerialException
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

schema = 'schema_1_2'

### TODO:
#       - Put together an array of the connection function
#       - Look into using Docker to create the right virtual machine to run this on 
#       - Determine appropriate tunnel time window

def light_loop(lightObj):
    t = threading.currentThread()
    while getattr(t, "do_run", True):
        lightObj.lightHeart()

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

def build_cloud_obj():
    ### Redundancy for Connecting to the Onboard Modem ###
    logging.info('Connecting to on-board modem and building new cloud object...')
    attempts = 1
    err = ""

    while attempts <= 4:
        cloud = None
        logging.info('- Modem Connection Attempt %i -', attempts)

        if attempts == 4:
            logging.critical('FATAL ERROR: %s', err)
            logging.critical('3 attempts made to connect to build cloud object')
            logging.critical('Sleeping until next cycle')
            sleep_time = sleep_calc(wake_time)
            rtc_wake(str(sleep_time), "standby")
            attempts = 0
            continue

        try:
            cloud = CustomCloud(None, network='cellular')
            break
        
        except NetworkError:
            logging.error('ERR101: Could not find modem')
            err = err + "E101; "
            rtc_wake("5", "standby")
            time.sleep(15)
            attempts += 1
            continue
        
        except SerialError:
            logging.error('ERR103: Could not find usable serial port')
            err = err + "E103; "
            rtc_wake("5", "standby")
            time.sleep(15)
            attempts += 1
            continue

    logging.info('--> Successfully found USB Modem')           
    return cloud, err    
        
def connect_cellular(cloud):
    ### Redundancy for Connecting to the Cellular Network ###
    logging.info('Connecting to Cellular Network...')    
    attempts = 1
    err = ""
    
    while attempts <= 4:
        logging.info('- Cellular Network Connection Attempt %i -', attempts)

        if attempts == 4:
            logging.critical('FATAL ERROR: %s', err)
            logging.critical('3 attempts made to connect to connect to cellular network')
            logging.critical('Sleeping until next cycle')
            sleep_time = sleep_calc(wake_time)
            rtc_wake(str(sleep_time), "standby")
            attempts = 0
            continue  
        
        try: 
            result = cloud.network.connect()

        except PPPError:
            logging.error('ERR105: Could not start a PPP Session -- Other Sessions still open')
            err = err + "E105; "
            
            if attempts < 2:
                clean_kill(cloud)
                cloud , errx = build_cloud_obj()
                err = err + errx
                antenna_cycle(cloud)
                attempts += 1
                continue
            
            else:
                clean_kill(cloud)
                rtc_wake("5", "standby")
                time.sleep(15)
                cloud , errx = build_cloud_obj()
                err = err + errx
                antenna_cycle(cloud)
                attempts += 1
                continue


        except SerialException:
            logging.error('ERR121: Modem reports readiness but returns no data')
            err = err + "E121; "
            
            if attempts < 2:
                clean_kill(cloud)
                cloud , errx = build_cloud_obj()
                err = err + errx
                antenna_cycle(cloud)
                attempts += 1
                continue
            
            else:
                clean_kill(cloud)
                rtc_wake("5", "standby")
                time.sleep(15)
                cloud , errx = build_cloud_obj()
                err = err + errx
                antenna_cycle(cloud)
                attempts += 1
                continue

        if result == True:
            break

        else:
            logging.error('ERR107: Could not connect to cellular network')
            err = err + "E107; "
            
            if attempts < 2:
                clean_kill(cloud)
                cloud , errx = build_cloud_obj()
                err = err + errx
                antenna_cycle(cloud)
                attempts += 1
                continue
            
            else:
                clean_kill(cloud)
                rtc_wake("5", "standby")
                time.sleep(15)
                cloud , errx = build_cloud_obj()
                err = err + errx
                antenna_cycle(cloud)
                attempts += 1
                continue

    logging.info('--> Successfully Connected to Cell Network')
    return cloud, err

def connect_mqtt(client, cloud):
    ### Redundancy for Connecting to MQTT Client ###
    logging.info('Connecting to MQTT...')
    attempts = 1
    err = ""

    while attempts <= 4:
        logging.info('- MQTT Client Connection Attempt %i -', attempts)

        if attempts == 4:
            logging.critical('FATAL ERROR: %s', err)
            logging.critical('3 attempts made to connect to connect to mqtt client')
            logging.critical('Sleeping until next cycle')
            sleep_time = sleep_calc(wake_time)
            rtc_wake(str(sleep_time), "standby")
            attempts = 0
            continue 

        try:
            result = client.connect()

        except gaierror:
            logging.error('ERR109: Temporary failure in DNS server name resolution')
            err = err + "E109; "
            clean_kill(cloud)
            rtc_wake("5", "standby")
            time.sleep(15)
            cloud , errx = build_cloud_obj()
            err = err + errx
            antenna_cycle(cloud)
            cloud, errx = connect_cellular(cloud)
            err = err + errx
            attempts += 1
            continue

        except connectTimeoutException:
            logging.error('ERR121: MQTT client connection timeout')
            err = err + "E121; "
            clean_kill(cloud)
            rtc_wake("5", "standby")
            time.sleep(15)
            cloud , errx = build_cloud_obj()
            err = err + errx
            antenna_cycle(cloud)
            cloud, errx = connect_cellular(cloud)
            err = err + errx
            attempts += 1
            continue
            
        if result == True:
            time.sleep(5)
            break
        else:
            logging.error('ERR111: Could not Connect to MQTT Client')
            err = err + "E111; "
            clean_kill(cloud)
            rtc_wake("5", "standby")
            time.sleep(15)
            cloud , errx = build_cloud_obj()
            err = err + errx
            antenna_cycle(cloud)
            cloud, errx = connect_cellular(cloud)
            err = err + errx
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

def clean_kill(cloud):
    ### Turns off and destroys all PPP sessions to the cellular network
    logging.info('Disconnecting All Sessions...')
    cloud.network.disconnect()

    for proc in psutil.process_iter():

        try:
            pinfo = proc.as_dict(attrs=['pid', 'name'])
        except:
            raise HologramError('Failed to check for existing PPP sessions')
        if 'pppd' in pinfo['name']:
            print('Found existing PPP session on pid: %s' % pinfo['pid'])
            print('Killing pid %s now' % pinfo['pid'])
            psutil.Process(pinfo['pid']).kill()
            print(kill_proc_tree(pinfo['pid']))
    
    time.sleep(5)

def kill_proc_tree(pid, sig=signal.SIGTERM, include_parent=True, timeout=None, on_terminate=None):
    """Kill a process tree (including grandchildren) with signal
    "sig" and return a (gone, still_alive) tuple.
    "on_terminate", if specified, is a callabck function which is
    called as soon as a child terminates.
    """
    assert pid != os.getpid(), "won't kill myself"
    parent = psutil.Process(pid)
    children = parent.children(recursive=True)
    
    if include_parent:
        children.append(parent)
    
    for p in children:
        p.send_signal(sig)
    
    gone, alive = psutil.wait_procs(children, timeout=timeout, callback=on_terminate)
    
    return (gone, alive)

def rtc_wake(time, mode):
    
    logging.warning('Soft Rebooting...')
    bashCommand = "sudo rtcwake --date +%isec -m %s"%(time, mode)
    process = subprocess.Popen(bashCommand.split(), stdout=subprocess.PIPE)
    output, error = process.communicate()

def antenna_cycle(cloud):
    
    logging.info('Cycling the radio antenna...')
    cloud.network.modem.radio_power(False)
    time.sleep(15)
    cloud.network.modem.radio_power(True)
    time.sleep(15)

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

    ### Start the program
    logging.info('###---------- Logi Cellular Program Start ----------###')

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
            ### Start cycle
            logging.info('Starting Cycle Number: %i', cycleCnt)
            err = ""
            led_red = CommandLED("P8_8")
            led_red.lightOn()

            ### Init Cloud Object
            cloud, errx = build_cloud_obj()
            err = err + errx

            ### Connect to Cellular Network
            cloud, errx = connect_cellular(cloud)
            err = err + errx

            ### Connect to MQTT Client
            cloud, errx = connect_mqtt(myAWSIoTMQTTClient, cloud)
            err = err + errx

            ### Turn on blue light
            led_blu = CommandLED("P8_7")
            led_blu.lightOn()

            ### Start connection light heartbeat
            LED_blu_t = threading.Thread(name='lightLoop', target=light_loop, args=(led_blu,))
            LED_blu_t.start()

            ### Init Board I/O
            logging.info('Initialing Board I/O...')
            try: 
                ADC.setup()
                lev     = FluidLevel("P9_39")
                mpl     = MPL3115A2()
                logging.info('--> Successfully Initialized I/O')
            except:
                logging.error('ERR115: Error initializing board I/O')
                err = err + "E115; "

            ### Record the RSSI
            try: 
                rssi = cloud.network.signal_strength
            except:
                logging.error('ERR117: Error getting RSSI values')
                rssi = "err"
                err = err + "E117; "
        
            ### Subscribe to MQTT Topics
            #myAWSIoTMQTTClient.subscribe("topic/devices/cast", 0, myCallbackContainer.messagePrint)

            ### Timestamp 
            timestamp = time.time()
            timelocal = time.strftime("%Y-%m-%d %H:%M:%S %Z", time.localtime())
            
            ### Get Temperature Data from MPL
            try:
                mpl.control_alt_config()
                mpl.data_config()
                mplTemp = mpl.read_alt_temp()

            except:
                logging.error('ERR119: I2C bus error')
                err = err + "E119; "
                mplTemp = {'a' : 999, 'c' : 999, 'f' : 999}

            ### Measure the battery level
            bat_lvl = 95

            wake_time = (next(sched_cycle))

            ### Set the MQTT Message
            JSONpayload = json.dumps(
                {'id': mqtt.thingName, 'ts': timestamp, 'ts_l': timelocal, 
                'schem': schema, 'wake': wake_time, 'cyc': str(cycleCnt), 'err': err, 
                'rssi': rssi, 'bat': bat_lvl, 'fuel': lev.getLev(), 'temp': mplTemp['c']})


            ### Publish to MQTT Broker
            topic = 'logi/devices/%s'%(mqtt.thingName)
            logging.info('Topic: %s', topic)
            logging.info('Published Message: %s', JSONpayload)
            myAWSIoTMQTTClient.publish(topic, JSONpayload, 0)
            cycleCnt = cycleCnt + 1
            
            ### Kill all open PPP connections and processes
            logging.info('Killing all PPP connections...')
            clean_kill(cloud)
            cloud = None
            time.sleep(5)
            
            ### Cycle LED's to OFF
            LED_blu_t.do_run = False
            LED_blu_t.join()
            led_blu.lightOff()
            led_red.lightOff()
            GPIO.cleanup()

            ### Bash Command to Enter Sleep Cycle
            logging.info('Wake up time: %s', wake_time)
            sleep_time = sleep_calc(wake_time)
            logging.info('Sleep time in sec: %s', str(sleep_time))
            rtc_wake(str(sleep_time), "mem")
            time.sleep(20)
    
        except KeyboardInterrupt:
            pass
            
    ### Turn Off LED and Clean Up GPIO Before Exiting
    LED_blu_t.do_run = False
    LED_blu_t.join()
    led_blu.lightOff()
    led_red.lightOff()
    
    GPIO.cleanup()
    logging.info('\n Program Terminated')

    os._exit(1)

if __name__=="__main__":
    main()