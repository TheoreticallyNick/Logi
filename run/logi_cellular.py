#!/usr/bin/env python

import sys, os, signal

#activate_this_file = "/var/lib/cloud9/Logi/bin/activate_this.py"
activate_this_file = "/home/debian/Desktop/Logi/bin/activate_this.py"
exec(compile(open(activate_this_file, "rb").read(), activate_this_file, 'exec'), dict(__file__=activate_this_file))

sys.path.append('/home/debian/Desktop/Logi/controls/')
#sys.path.append('/var/lib/cloud9/Logi/controls/')
sys.path.append('/home/debian/Desktop/keys/')

import threading
import time
import logging
import subprocess
from socket import gaierror
import psutil
from datetime import datetime
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

### TODO:
#       - Put together an array of the connection function
#       - Use a pointer function to start from a certain spot in the connection array
#       - Look into using Docker to create the right virtual machine to run this on 
#       - Check out pyenv and pipenv and json.dump
#       - Using dict() and **kwargs to setup the mqtt message

def lightLoop(lightObj):
    t = threading.currentThread()
    while getattr(t, "do_run", True):
        lightObj.lightHeart()

def buildCloudObject():
    ### Redundancy for Connecting to the Onboard Modem ###
    logging.info('Connecting to on-board modem and building new cloud object...')
    attempts = 1
    err = ""

    while attempts <= 4:
        cloud = None
        logging.info('- Modem Connection Attempt %i -', attempts)

        if attempts == 4:
            logging.critical('FATAL ERROR: %s', err)
            logging.critical('3 attempts made to connect to MQTT Client')
            os._exit(1)  

        try:
            cloud = CustomCloud(None, network='cellular')
            break
        
        except NetworkError:
            logging.error('ERR101: Could not find modem')
            err = err + "E101; "
            rtcWake("5", "standby")
            time.sleep(15)
            attempts += 1
            continue
        
        except SerialError:
            logging.error('ERR103: Could not find usable serial port')
            err = err + "E103; "
            rtcWake("5", "standby")
            time.sleep(15)
            attempts += 1
            continue

    logging.info('--> Successfully found USB Modem')           
    return cloud, err    
        
def connectToCellular(cloud):
    ### Redundancy for Connecting to the Cellular Network ###
    logging.info('Connecting to Cellular Network...')    
    attempts = 1
    err = ""
    
    while attempts <= 4:
        logging.info('- Cellular Network Connection Attempt %i -', attempts)

        if attempts == 4:
            logging.critical('FATAL ERROR: %s', err)
            logging.critical('3 attempts made to connect to MQTT Client')
            os._exit(1)  
        
        try: 
            result = cloud.network.connect()

        except PPPError:
            logging.error('ERR105: Could not start a PPP Session -- Other Sessions still open')
            err = err + "E105; "
            
            if attempts < 2:
                cleanKill(cloud)
                cloud , errx = buildCloudObject()
                err = err + errx
                antennaCycle(cloud)
                attempts += 1
                continue
            
            else:
                cleanKill(cloud)
                rtcWake("5", "standby")
                time.sleep(15)
                cloud , errx = buildCloudObject()
                err = err + errx
                antennaCycle(cloud)
                attempts += 1
                continue


        except SerialException:
            logging.error('ERR121: Modem reports readiness but returns no data')
            err = err + "E121; "
            
            if attempts < 2:
                cleanKill(cloud)
                cloud , errx = buildCloudObject()
                err = err + errx
                antennaCycle(cloud)
                attempts += 1
                continue
            
            else:
                cleanKill(cloud)
                rtcWake("5", "standby")
                time.sleep(15)
                cloud , errx = buildCloudObject()
                err = err + errx
                antennaCycle(cloud)
                attempts += 1
                continue

        if result == True:
            break

        else:
            logging.error('ERR107: Could not connect to cellular network')
            err = err + "E107; "
            
            if attempts < 2:
                cleanKill(cloud)
                cloud , errx = buildCloudObject()
                err = err + errx
                antennaCycle(cloud)
                attempts += 1
                continue
            
            else:
                cleanKill(cloud)
                rtcWake("5", "standby")
                time.sleep(15)
                cloud , errx = buildCloudObject()
                err = err + errx
                antennaCycle(cloud)
                attempts += 1
                continue

    logging.info('--> Successfully Connected to Cell Network')
    return cloud, err

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
            cleanKill(cloud)
            rtcWake("5", "standby")
            time.sleep(15)
            cloud , errx = buildCloudObject()
            err = err + errx
            antennaCycle(cloud)
            cloud, errx = connectToCellular(cloud)
            err = err + errx
            attempts += 1
            continue

        except connectTimeoutException:
            logging.error('ERR121: MQTT client connection timeout')
            err = err + "E121; "
            cleanKill(cloud)
            rtcWake("5", "standby")
            time.sleep(15)
            cloud , errx = buildCloudObject()
            err = err + errx
            antennaCycle(cloud)
            cloud, errx = connectToCellular(cloud)
            err = err + errx
            attempts += 1
            continue
            
        if result == True:
            time.sleep(5)
            break
        else:
            logging.error('ERR111: Could not Connect to MQTT Client')
            err = err + "E111; "
            cleanKill(cloud)
            rtcWake("5", "standby")
            time.sleep(15)
            cloud , errx = buildCloudObject()
            err = err + errx
            antennaCycle(cloud)
            cloud, errx = connectToCellular(cloud)
            err = err + errx
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

def cleanKill(cloud):
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

def rtcWake(time, mode):
    
    logging.warning('Soft Rebooting...')
    bashCommand = "sudo rtcwake -u -s %s -m %s"%(time, mode)
    process = subprocess.Popen(bashCommand.split(), stdout=subprocess.PIPE)
    output, error = process.communicate()

def antennaCycle(cloud):
    
    logging.info('Cycling the radio antenna...')
    cloud.network.modem.radio_power(False)
    time.sleep(15)
    cloud.network.modem.radio_power(True)
    time.sleep(15)

def main():

    ### Set up the logger
    logging.basicConfig(filename='logi_runtime.log', filemode='w', format='%(asctime)s -- %(levelname)s: %(message)s', level=logging.INFO)
    console = logging.StreamHandler()
    console.setLevel(logging.INFO)
    logging.getLogger('').addHandler(console)

    logging.info('###---------- Logi Cellular Program Start ----------###')

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
            ### Start cycle
            logging.info('Starting Cycle Number: %i', cycleCnt)
            err = ""
            led_red = CommandLED("P8_8")
            led_red.lightOn()

            ### Init Cloud Object
            cloud, errx = buildCloudObject()
            err = err + errx

            ### Connect to Cellular Network
            cloud, errx = connectToCellular(cloud)
            err = err + errx

            ### Connect to MQTT Client
            cloud, errx = connectMQTT(myAWSIoTMQTTClient, cloud)
            err = err + errx

            ### Turn on blue light
            led_blu = CommandLED("P8_7")
            led_blu.lightOn()

            ### Start connection light heartbeat
            LED_blu_t = threading.Thread(name='lightLoop', target=lightLoop, args=(led_blu,))
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


            ### Set the MQTT Message
            JSONpayload = '{"id": "%s", "ts": "%s", "ts_l": "%s", "schem": "1.2", "slp": "%s", "cyc": "%s", "err": "%s", "rssi": "%s", "bat": "bat, "lvl": %.2f, "temp": %.2f}'%(mqtt.thingName, timestamp, timelocal, sleepTime, str(cycleCnt), err, rssi, lev.getLev(), mplTemp['c'])
            
            ### Publish to MQTT Broker
            myAWSIoTMQTTClient.publish("topic/devices/data", JSONpayload, 0)
            topic = 'logi/devices/%s'%(mqtt.thingName)
            logging.info('Topic: %s', topic)
            logging.info('Published Message: %s', JSONpayload)
            time.sleep(5)
            cycleCnt = cycleCnt + 1
            
            ### Kill all open PPP connections and processes
            logging.info('Killing all PPP connections...')
            cleanKill(cloud)
            cloud = None
            time.sleep(5)
            
            ### Cycle LED's to OFF
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
    logging.info('\n Program Terminated')

    os._exit(1)

if __name__=="__main__":
    main()