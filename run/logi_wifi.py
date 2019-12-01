#!/usr/bin/env python
#Logi v2.1

import sys, os, signal

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
from DS1318 import FluidLevel
import Adafruit_BBIO.GPIO as GPIO
import Adafruit_BBIO.ADC as ADC
import threading
import time
from datetime import datetime
import subprocess
from socket import gaierror

def lightLoop(lightObj):
    t = threading.currentThread()
    while getattr(t, "do_run", True):
        lightObj.lightHeart()

def connectMQTT(client, cloud):
    ### Redundancy for Connecting to MQTT Client ###
    print("Connecting to MQTT...")
    attempts = 1
    err = ""

    while attempts < 6:
        print("- MQTT Client Connection Attempt %i -"%(attempts))
        time.sleep(10)

        try:
            result = client.connect()

        except gaierror:
            print("ERR109: Temporary failure in DNS server name resolution")
            err = err + "E109; "
            time.sleep(30)
            continue

        except connectTimeoutException:
            print("ERR121: MQTT client connection timeout")
            err = err + "E121; "
            time.sleep(30)
            continue
        
        if result == True:
            print("--> Successfully Connected to MQTT Client")
            break
        else:
            print("ERR111: Could not Connect to MQTT Client")
            err = err + "E111; "
            time.sleep(30)
        
        attempts += 1

    if attempts == 5:
        print("FATAL ERROR: " + err)
        os._exit(1)  

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

def main():

    print("###---------- Logi Wifi Program Start ----------###")
    sleepTime = (input("Sleep Time in Seconds: "))
    cycleCnt = 1

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
            time.sleep(90)
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

            ### Init Board I/O
            print("Initialing Board I/O...")
            try: 
                ADC.setup()
                pres   = Pressure("P9_39")
                temp   = Thermocouple("P9_40")
                lev     = 0 #FluidLevel("P9_39")
                mpl     = MPL3115A2()
                print("--> Successfully Initialized I/O")
            except:
                print("ERR115: Error Initializing Board I/O; ")
                err = err + "E115; "            
        
            #myAWSIoTMQTTClient.subscribe("topic/devices/cast", 0, myCallbackContainer.messagePrint)
            
            ### MQTT Message build and publish
            
            timestamp = time.time()
            timelocal = datetime.utcfromtimestamp(timestamp).strftime('%Y-%m-%d %H:%M:%S')
            
            try:
                mpl.control_alt_config()
                mpl.data_config()
                mplTemp = mpl.read_alt_temp()
                rssi = "null"

            except:
                print("ERR119: I2C Bus Error")
                err = err + "E119; "
                mplTemp = {'a' : 999, 'c' : 999, 'f' : 999}

            JSONpayload = '{"id": "%s", "ts": "%s", "ts_l": "%s", "schema": "mqtt_v1", "cycle": "%s", "error": "%s", "RSSI": "%s", "temp_v": %.2f, "pres": %.2f, "MPL_c": %.2f, "MPL_f": %.2f}'%(mqtt.thingName, timestamp, timelocal, str(cycleCnt), err, rssi, temp.getVoltage(), pres.getPres(), mplTemp['c'], mplTemp['f'])
            myAWSIoTMQTTClient.publish("topic/devices/data", JSONpayload, 0)
            print("Published Message: " + JSONpayload)
            cycleCnt = cycleCnt + 1

            ### Turn Off LED and Clean Up GPIO Before Exiting
            LED_blu_t.do_run = False
            LED_blu_t.join()
            led_blu.lightOff()
            led_red.lightOff()
            GPIO.cleanup()
            
            ### Bash Command to Enter Sleep Cycle
            print("Going to Sleep for %s seconds"%(str(sleepTime)))
            bashCommand = "sudo rtcwake -u -s " + (str(sleepTime)) + " -m standby"
            print("@bash: sudo rtcwake -u -s " + (str(sleepTime)) + " -m standby")
            process = subprocess.Popen(bashCommand.split(), stdout=subprocess.PIPE)
            output, error = process.communicate()
            
    
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