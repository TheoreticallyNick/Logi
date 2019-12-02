#!/usr/bin/env python
#Logi v2.1

import sys, os, signal

#activate_this_file = "/var/lib/cloud9/Logi/bin/activate_this.py"
activate_this_file = "/home/debian/Desktop/Logi/bin/activate_this.py"
exec(compile(open(activate_this_file, "rb").read(), activate_this_file, 'exec'), dict(__file__=activate_this_file))

sys.path.append('/home/debian/Desktop/Logi/controls/')
#sys.path.append('/var/lib/cloud9/Logi/controls/')
sys.path.append('/home/debian/Desktop/keys/')

from MQTTconnect import ConnectMQTTParams
from MQTTconnect import CallbackContainer
from AWSIoTPythonSDK.MQTTLib import AWSIoTMQTTClient
from AWSIoTPythonSDK.exception.AWSIoTExceptions import *
from LED import CommandLED
from AD8 import Thermocouple
from PX3 import Pressure
from MPL import MPL3115A2
from DS1318 import FluidLevel
import Adafruit_BBIO.GPIO as GPIO
import Adafruit_BBIO.ADC as ADC
import threading
import time
import subprocess
from socket import gaierror
import psutil
from datetime import datetime
from serial import SerialException
from Hologram.Network import Network, Cellular
from Hologram.HologramCloud import HologramCloud
from Hologram.CustomCloud import CustomCloud
from Exceptions.HologramError import NetworkError, PPPError, SerialError, HologramError

def lightLoop(lightObj):
    t = threading.currentThread()
    while getattr(t, "do_run", True):
        lightObj.lightHeart()

def buildCloudObject():
    ### Redundancy for Connecting to the Onboard Modem ###
    print("Connecting to On-Board Modem...")
    attempts = 1
    err = ""

    while attempts <= 4:
        cloud = None
        print("- Modem Connection Attempt %i -"%(attempts))

        if attempts == 4:
            print("FATAL ERROR: " + err)
            print("3 attempts made to connect to MQTT Client")
            os._exit(1)  

        try:
            cloud = CustomCloud(None, network='cellular')
            break
        
        except NetworkError:
            print("ERR101: Could not find modem")
            err = err + "E101; "
            print("Soft Rebooting...")
            rtcWake("5", "standby")
            time.sleep(15)
            attempts += 1
            continue
        
        except SerialError:
            print("ERR103: Could not find usable serial port")
            err = err + "E103; "
            print("Soft Rebooting...")
            rtcWake("5", "standby")
            time.sleep(15)
            attempts += 1
            continue

    print("--> Successfully found USB Modem")           
    return cloud, err    
        
def connectToCellular(cloud):
    ### Redundancy for Connecting to the Cellular Network ###
    print("Connecting to Cellular Network...")
    attempts = 1
    err = ""
    
    while attempts <= 4:
        print("- Cellular Network Connection Attempt %i -"%(attempts))

        if attempts == 4:
            print("FATAL ERROR: " + err)
            print("3 attempts made to connect to MQTT Client")
            os._exit(1)  
        
        try: 
            result = cloud.network.connect()

        except PPPError:
            print("ERR105: Could not start a PPP Session -- Other Sessions still open")
            err = err + "E105; "
            
            if attempts < 2:
                print("Disconnecting All Sessions...")
                cleanKill(cloud)
                print("Building new cloud object...")
                cloud , errx = buildCloudObject()
                err = err + errx
                print("Cycling the radio antenna...")
                cloud.network.modem.radio_power(False)
                time.sleep(15)
                cloud.network.modem.radio_power(True)
                time.sleep(15)
                attempts += 1
                continue
            
            else:
                print("Disconnecting All Sessions...")
                cleanKill(cloud)
                print("Soft Rebooting...")
                rtcWake("5", "standby")
                time.sleep(15)
                print("Building new cloud object...")
                cloud , errx = buildCloudObject()
                err = err + errx
                print("Cycling the radio antenna...")
                cloud.network.modem.radio_power(False)
                time.sleep(15)
                cloud.network.modem.radio_power(True)
                time.sleep(15)
                attempts += 1
                continue


        except SerialException:
            print("ERR121: Modem reports readiness but returns no data")
            err = err + "E121; "
            
            if attempts < 2:
                print("Disconnecting All Sessions...")
                cleanKill(cloud)
                print("Building new cloud object...")
                cloud , errx = buildCloudObject()
                err = err + errx
                print("Cycling the radio antenna...")
                cloud.network.modem.radio_power(False)
                time.sleep(15)
                cloud.network.modem.radio_power(True)
                time.sleep(15)
                attempts += 1
                continue
            
            else:
                print("Disconnecting All Sessions...")
                cleanKill(cloud)
                print("Soft Rebooting...")
                rtcWake("5", "standby")
                time.sleep(15)
                print("Building new cloud object...")
                cloud , errx = buildCloudObject()
                err = err + errx
                print("Cycling the radio antenna...")
                cloud.network.modem.radio_power(False)
                time.sleep(15)
                cloud.network.modem.radio_power(True)
                time.sleep(15)
                attempts += 1
                continue

        if result == True:
            break

        else:
            print("ERR107: Could not connect to cellular network")
            err = err + "E107; "
            
            if attempts < 2:
                print("Disconnecting All Sessions...")
                cleanKill(cloud)
                print("Building new cloud object...")
                cloud , errx = buildCloudObject()
                err = err + errx
                print("Cycling the radio antenna...")
                cloud.network.modem.radio_power(False)
                time.sleep(15)
                cloud.network.modem.radio_power(True)
                time.sleep(15)
                attempts += 1
                continue
            
            else:
                print("Disconnecting All Sessions...")
                cleanKill(cloud)
                print("Soft Rebooting...")
                rtcWake("5", "standby")
                time.sleep(15)
                print("Building new cloud object...")
                cloud , errx = buildCloudObject()
                err = err + errx
                print("Cycling the radio antenna...")
                cloud.network.modem.radio_power(False)
                time.sleep(15)
                cloud.network.modem.radio_power(True)
                time.sleep(15)
                attempts += 1
                continue

    print("--> Successfully Connected to Cell Network")
    return cloud, err

def connectMQTT(client, cloud):
    ### Redundancy for Connecting to MQTT Client ###
    print("Connecting to MQTT...")
    attempts = 1
    err = ""

    while attempts <= 4:
        print("- MQTT Client Connection Attempt %i -"%(attempts))

        if attempts == 4:
            print("FATAL ERROR: " + err)
            print("3 attempts made to connect to MQTT Client")
            os._exit(1)  

        try:
            result = client.connect()

        except gaierror:
            print("ERR109: Temporary failure in DNS server name resolution")
            print("Check if there is a wifi connection")
            err = err + "E109; "
            print("Disconnecting All Sessions...")
            cleanKill(cloud)
            print("Soft Rebooting...")
            rtcWake("5", "standby")
            time.sleep(15)
            print("Building new cloud object...")
            cloud , errx = buildCloudObject()
            err = err + errx
            print("Cycling the radio antenna...")
            cloud.network.modem.radio_power(False)
            time.sleep(15)
            cloud.network.modem.radio_power(True)
            time.sleep(15)
            cloud, errx = connectToCellular(cloud)
            err = err + errx
            attempts += 1
            continue

        except connectTimeoutException:
            print("ERR121: MQTT client connection timeout")
            err = err + "E121; "
            print("Disconnecting All Sessions...")
            cleanKill(cloud)
            print("Soft Rebooting...")
            rtcWake("5", "standby")
            time.sleep(15)
            print("Building new cloud object...")
            cloud , errx = buildCloudObject()
            err = err + errx
            print("Cycling the radio antenna...")
            cloud.network.modem.radio_power(False)
            time.sleep(15)
            cloud.network.modem.radio_power(True)
            time.sleep(15)
            cloud, errx = connectToCellular(cloud)
            err = err + errx
            attempts += 1
            continue
            
        if result == True:
            time.sleep(5)
            break
        else:
            print("ERR111: Could not Connect to MQTT Client")
            err = err + "E111; "
            print("Disconnecting All Sessions...")
            cleanKill(cloud)
            print("Soft Rebooting...")
            rtcWake("5", "standby")
            time.sleep(15)
            print("Building new cloud object...")
            cloud , errx = buildCloudObject()
            err = err + errx
            print("Cycling the radio antenna...")
            cloud.network.modem.radio_power(False)
            time.sleep(15)
            cloud.network.modem.radio_power(True)
            time.sleep(15)
            cloud, errx = connectToCellular(cloud)
            err = err + errx
            attempts += 1
            continue

    time.sleep(5)
    hostname = "google.com"
    response = os.system("ping -c 1 " + hostname)
    
    if response == 0:
        print("Pinging Successfully...")
    else:
        print("Unable to Ping...")  

    print("--> Successfully Connected to MQTT Client")
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
        print("--> Successfully Initialized!")
    except:
        print("ERR113: Error Initializing MQTT Connection Parameters")
        err = err + "E113; "
        os._exit(1)
    
    return myAWSIoTMQTTClient

def cleanKill(cloud):
    ### Turns off and destroys all PPP sessions to the cellular network
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

    bashCommand = "sudo rtcwake -u -s %s -m %s"%(time, mode)
    process = subprocess.Popen(bashCommand.split(), stdout=subprocess.PIPE)
    output, error = process.communicate()

def main():

    print("###---------- Logi 2.1 Program Start ----------###")
    sleepTime = (input("Sleep Time in Seconds: "))
    cycleCnt = 1
    led_red = CommandLED("P8_8")
    led_red.lightOn()

    ### Set timezone
    os.environ['TZ'] = 'US/Eastern'
    time.tzset()  
    
    ### Init AWSIoTMQTTClient
    print("Initializing MQTT Connection Parameters...")
    mqtt = ConnectMQTTParams()
    myAWSIoTMQTTClient = initMQTTClient(mqtt)
        
    while True:

        try:
            err = ""

            ### Init Cloud Object
            cloud, errx = buildCloudObject()
            err = err + errx

            ### Connect to Cellular Network
            cloud, errx = connectToCellular(cloud)
            err = err + errx

            ### Connect to MQTT Client
            if cycleCnt == 1:
                cloud, errx = connectMQTT(myAWSIoTMQTTClient, cloud)
                err = err + errx

            ### Init Board I/O
            print("Initialing Board I/O...")
            try: 
                ADC.setup()
                #pres   = Pressure("P9_39")
                #temp   = Thermocouple("P9_40")
                lev     = FluidLevel("P9_39")
                mpl     = MPL3115A2()
                print("--> Successfully Initialized I/O")
            except:
                print("ERR115: Error Initializing Board I/O; ")
                err = err + "E115; "

            try: 
                rssi = cloud.network.signal_strength
            except:
                print("ERR117: Error getting RSSI Values; ")
                rssi = "err"
                err = err + "E117; "
                
            ### Turn on blue light
            led_blu = CommandLED("P8_7")
            led_blu.lightOn()
        
            ### Start connection light heartbeat
            LED_blu_t = threading.Thread(name='lightLoop', target=lightLoop, args=(led_blu,))
            LED_blu_t.start()
        
            #myAWSIoTMQTTClient.subscribe("topic/devices/cast", 0, myCallbackContainer.messagePrint)
            
            ### MQTT Message build and publish
            
            timestamp = time.time()
            timelocal = time.strftime("%Y-%m-%d %H:%M:%S %Z", time.localtime())
            
            try:
                mpl.control_alt_config()
                mpl.data_config()
                mplTemp = mpl.read_alt_temp()

            except:
                print("ERR119: I2C Bus Error")
                err = err + "E119; "
                mplTemp = {'a' : 999, 'c' : 999, 'f' : 999}

            time.sleep(5)
            JSONpayload = '{"id": "%s", "ts": "%s", "ts_l": "%s", "schema": "mqtt_v1", "cycle": "%s", "error": "%s", "RSSI": "%s", "DS1318_volts": %.2f, "Fluid_per": %.2f, "MPL_c": %.2f, "MPL_f": %.2f}'%(mqtt.thingName, timestamp, timelocal, str(cycleCnt), err, rssi, lev.getVoltage(), lev.getLev(), mplTemp['c'], mplTemp['f'])
            myAWSIoTMQTTClient.publish("topic/devices/data", JSONpayload, 0)
            print("Published Message: " + JSONpayload)
            time.sleep(5)
            cycleCnt = cycleCnt + 1
            
            print("Killing all PPP connections...")
            cleanKill(cloud)
            cloud = None
            time.sleep(5)
            
            ### Bash Command to Enter Sleep Cycle
            print("Going to Sleep for %s seconds"%(str(sleepTime)))
            rtcWake(str(sleepTime), "standby")
            time.sleep(20)
    
        except KeyboardInterrupt:
            pass
            
    ### Turn Off LED and Clean Up GPIO Before Exiting
    LED_blu_t.do_run = False
    LED_blu_t.join()
    led_red.lightOff()
    led_red.lightOff()
    
    GPIO.cleanup()
    print("\n Program Terminated")

    os._exit(1)

if __name__=="__main__":
    main()