#!/usr/bin/env python
#Logi v2.1

import sys, os

#activate_this_file = "/var/lib/cloud9/Logi/bin/activate_this.py"
activate_this_file = "/home/debian/Desktop/Logi/bin/activate_this.py"
exec(compile(open(activate_this_file, "rb").read(), activate_this_file, 'exec'), dict(__file__=activate_this_file))

sys.path.append('/home/debian/Desktop/Logi/controls/')
#sys.path.append('/var/lib/cloud9/Logi/controls/')
sys.path.append('/home/debian/Desktop/keys/')
from MQTTconnect import ConnectMQTTParams
from MQTTconnect import CallbackContainer
from AWSIoTPythonSDK.MQTTLib import AWSIoTMQTTClient
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
from Hologram.Network import Network, Cellular
from Hologram.HologramCloud import HologramCloud
from Hologram.CustomCloud import CustomCloud
from Exceptions.HologramError import NetworkError, PPPError, SerialError

def lightLoop(lightObj):
    t = threading.currentThread()
    while getattr(t, "do_run", True):
        lightObj.lightHeart()

def buildCloudObject():
    ### Redundancy for Connecting to the Onboard Modem ###
    print("Connecting to On-Board Modem...")
    attempts = 1
    err = ""

    while attempts < 5:
        cloud = None
        time.sleep(20)
        print("- Modem Connection Attempt %i -"%(attempts))
        try:
            cloud = CustomCloud(None, network='cellular')
            print("--> Successfully found USB Modem")
            break
        except NetworkError:
            print("ERR101: Could not find modem")
            err = err + "ERR101; "
            print("Soft Rebooting...")
            attempts += 1
            bashCommand = "sudo rtcwake -u -s 5 -m standby"
            process = subprocess.Popen(bashCommand.split(), stdout=subprocess.PIPE)
            output, error = process.communicate()
        except SerialError:
            print("ERR103: Could not find usable serial port")
            err = err + "ERR103; "
            attempts += 1
            if attempts > 2:
                print("Soft Rebooting...")
                bashCommand = "sudo rtcwake -u -s 5 -m standby"
                process = subprocess.Popen(bashCommand.split(), stdout=subprocess.PIPE)
                output, error = process.communicate()
                continue
            else:
                print("Disconnecting ALL Sessions")
                bashCommand = "sudo hologram network disconnect"
                process = subprocess.Popen(bashCommand.split(), stdout=subprocess.PIPE)
                output, error = process.communicate()

    if attempts >= 4:
        sys.exit("FATAL ERROR: " + err)
    else:           
        return cloud    
        
def connectToCellular(cloud):
    ### Redundancy for Connecting to the Cellular Network ###
    print("Connecting to Cellular Network...")
    attempts = 1
    err = ""
    cloud = cloud

    while attempts < 4:
        time.sleep(5)
        print("- Cellular Network Connection Attempt %i -"%(attempts))
        result = cloud.network.connect()
        if result == True:
            print("--> Successfully Connected to Cell Network")
            break
        else:
            print("ERR105: Could not create a new PPP Session")
            err = err + "ERR105; "
            print("Sleeping for 1 hours and Soft Rebooting...")
            attempts += 1
            bashCommand = "sudo rtcwake -u -s 3600 -m standby"
            process = subprocess.Popen(bashCommand.split(), stdout=subprocess.PIPE)
            output, error = process.communicate()
            cloud = buildCloudObject()

    if attempts >= 3:
        sys.exit("FATAL ERROR: " + err) 

    return cloud 

def connectMQTT(client, cloud):
    ### Redundancy for Connecting to MQTT Client ###
    print("Connecting to MQTT...")
    attempts = 1
    err = ""
    cloud = cloud

    while attempts < 4:
        print("- MQTT Client Connection Attempt %i -"%(attempts))
        result = client.connect()
        if result == True:
            print("--> Successfully Connected to MQTT Client")
            break
        else:
            print("ERR107: Could not Connect to MQTT Client")
            err = err + "ERR107; "
            print("Sleeping for 1 hour and Soft Rebooting...")
            attempts += 1
            bashCommand = "sudo rtcwake -u -s 3600 -m standby"
            process = subprocess.Popen(bashCommand.split(), stdout=subprocess.PIPE)
            output, error = process.communicate()
            cloud = buildCloudObject()
            cloud = connectToCellular(cloud)

    if attempts >= 3:
        sys.exit("FATAL ERROR: " + err)
    
    return cloud    

def main():

    print("###---------- Logi 2.1 Program Start ----------###")
    sleepTime = (input("Sleep Time in Seconds: "))
    cycleCnt = 1
    led_red = CommandLED("P8_8")
    led_red.lightOn()

    cloud = buildCloudObject()
    cloud = connectToCellular(cloud)

    ### Set timezone
    os.environ['TZ'] = 'US/Eastern'
    time.tzset()    
    
    ### Init AWSIoTMQTTClient
    print("Initializing MQTT Connection Parameters...")
    mqtt = ConnectMQTTParams()
    try:
        myAWSIoTMQTTClient = None
        myAWSIoTMQTTClient = AWSIoTMQTTClient(mqtt.mqttClientId)
        myAWSIoTMQTTClient.configureEndpoint(mqtt.host, mqtt.port)
        myAWSIoTMQTTClient.configureCredentials(mqtt.rootCAPath, mqtt.privateKeyPath, mqtt.certificatePath)
        myAWSIoTMQTTClient.configureAutoReconnectBackoffTime(1, 32, 20)
        myAWSIoTMQTTClient.configureConnectDisconnectTimeout(10)  # 10 sec
        myAWSIoTMQTTClient.configureMQTTOperationTimeout(5)  # 5 sec
        myCallbackContainer = CallbackContainer(myAWSIoTMQTTClient)
        print("--> Successfully Initialized!")
    except:
        print("ERROR 101: Error Initializing MQTT Connection Parameters -- Check your Keys")
        os._exit(1)

    ### Connect to AWS IoT
    cloud = connectMQTT(myAWSIoTMQTTClient, cloud)
        
    while True:
        if cycleCnt != 1:     
            time.sleep(900)
        err = ""
        ### Init Board I/O
        print("Initialing Board I/O...")
        try: 
            ADC.setup()
            print("--> Successfully Initialized I/O")
        except:
            print("ERROR 103: Error Initializing Board I/O; ")
            err = err + "ERROR 103; "

        #pres   = Pressure("P9_39")
        #temp   = Thermocouple("P9_40")
        lev    = FluidLevel("P9_39")
        mpl = MPL3115A2()

        #rssi = cloud.network.signal_strength

        try: 
            rssi = cloud.network.signal_strength
        except:
            print("ERROR 1XX: Error getting RSSI Values; ")
            rssi = "err"
            err = err + "ERROR 10x; "
            
        ### Turn on blue light
        led_blu = CommandLED("P8_7")
        led_blu.lightOn()
    
        ### Start connection light heartbeat
        LED_blu_t = threading.Thread(name='lightLoop', target=lightLoop, args=(led_blu,))
        LED_blu_t.start()
    
        #myAWSIoTMQTTClient.subscribe("topic/devices/cast", 0, myCallbackContainer.messagePrint)
        
        ### MQTT Message build and publish
        try: 
            timestamp = time.time()
            timelocal = time.strftime("%a, %d %b %Y %H:%M:%S %Z", time.localtime())
            
            try:
                mpl.control_alt_config()
                mpl.data_config()
                mplTemp = mpl.read_alt_temp()

            except:
                print("ERROR 107: I2C Bus Error")
                err = err + "ERROR 107; "
                mplTemp = {'a' : 999, 'c' : 999, 'f' : 999}
    
            JSONpayload = '{"id": "%s", "ts": "%s", "ts_l": "%s", "schema": "mqtt_v1", "cycle": "%s", "error": "%s", "RSSI": "%s", "DS1318_volts": %.2f, "Fluid_per": %.2f, "MPL_c": %.2f, "MPL_f": %.2f}'%(mqtt.thingName, timestamp, timelocal, str(cycleCnt), err, rssi, lev.getVoltage(), lev.getLev(), mplTemp['c'], mplTemp['f'])
            myAWSIoTMQTTClient.publish("topic/devices/data", JSONpayload, 0)
            print("Published Message: " + JSONpayload)
            cycleCnt = cycleCnt + 1
            
            time.sleep(5)
            print("Going to Sleep for %s seconds"%(str(sleepTime)))
            
            ### Disconnect from the Network
            #try:
                #cloud.network.disconnect()
                #disconnectCommand = "sudo hologram network disconnect"
                #print("@bash: sudo hologram network disconnect")
                #process = subprocess.Popen(disconnectCommand.split(), stdout=subprocess.PIPE)
                #print('PPP session ended')
            #except:
                #print("ERROR 111: Unable to Disconnect Modem; ")
            
            ### Bash Command to Enter Sleep Cycle
            #bashCommand = "sudo rtcwake -u -s " + (sleepTime) + " -m standby"
            #print("@bash: sudo rtcwake -u -s " + (sleepTime) + " -m standby")
            #process = subprocess.Popen(bashCommand.split(), stdout=subprocess.PIPE)
            #output, error = process.communicate()
    
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