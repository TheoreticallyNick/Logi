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

def lightLoop(lightObj):
    t = threading.currentThread()
    while getattr(t, "do_run", True):
        lightObj.lightHeart()

def main():
        
    led_red = CommandLED("P8_8")
    led_red.lightOn()

    print("###---------- Logi 2.1 Program Start ----------###")
    sleepTime = (input("Sleep Time in Seconds: "))

    cycleCnt = 1

    while True:
        
        if cycleCnt != 1:
            print("Waking up Logi...")
        
        time.sleep(15)
        led_red = CommandLED("P8_8")
        led_red.lightOn()
        
        err = ""
        
        print("Connecting to Cellular Network...")

        ### Set up Hologram Custom Cloud Object
        cloud = CustomCloud(None, network='cellular')
        
        ### Turn Off Radio
        res = cloud.network.modem.radio_power(False)
        if res:
            print('Modem radio disabled')
        else:
            print('Failure to disable radio')

        time.sleep(10)

        ### Turn On Radio
        res = cloud.network.modem.radio_power(True)
        if res:
            print('Modem radio enabled')
        else:
            print('Failure to enable radio')
        
        time.sleep(10)
        
        res = cloud.network.connect()
        if res:
            print('PPP session started')
        else:
            print('Failed to start PPP')
            print("ERROR 109: Unable to Connect Modem; ")

        time.sleep(20)
    
        ### Turn on power light (red LED)
        
        mqtt = ConnectMQTTParams()
        
        ### Set timezone
        os.environ['TZ'] = 'US/Eastern'
        time.tzset()    
        #print("Timezone set to EST")
    
        
        ### Init AWSIoTMQTTClient
        print("Initializing MQTT Connection Parameters...")
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
            err = err + "ERROR 101: Error Initializing MQTT Connection Parameters -- Check your Keys; "
            os._exit(1)
    
        
        ### Init Board I/O
        print("Initialing Board I/O...")
        try: 
            ADC.setup()
            #pres   = Pressure("P9_39")
            #temp   = Thermocouple("P9_40")
            lev    = FluidLevel("P9_39")
            rssi = (cloud.network.signal_strength)
            mpl = MPL3115A2()
            print("--> Successfully Initialized I/O")
        except:
            print("ERROR 103: Error Initializing Board I/O; ")
            err = err + "ERROR 103: Error Initializing Board I/O; "
            
        ### Turn on blue light
        led_blu = CommandLED("P8_7")
        led_blu.lightOn()
        
        ### Connect to AWS IoT
        print("Connecting to MQTT...")
        time.sleep(10)
        
        MQTTcon = None
        attempt = 0
        while MQTTcon is None:
            attempt = 1
            try:    
                myAWSIoTMQTTClient.connect()
                print("--> Successfully Connected")
                MQTTcon = True
            except: 
                print("ERROR 105: Error connecting to MQTT Client - Attempt %i"%(attempt))
                err = err + "ERROR 105: Error connecting to MQTT Client - Attempts %i; "%(attempt)
                attempt = attempt + 1
                pass
    
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
                err = err + "ERROR 107: I2C Bus Error; "
                mplTemp = {'a' : 999, 'c' : 999, 'f' : 999}
    
            JSONpayload = '{"id": "%s", "ts": "%s", "ts_l": "%s", "schema": "mqtt_v1", "cycle": "%s", "error": "%s", "RSSI": "%s", "DS1318_volts": %.2f, "Fluid_per": %.2f, "MPL_c": %.2f, "MPL_f": %.2f}'%(mqtt.thingName, timestamp, timelocal, str(cycleCnt), err, rssi, lev.getVoltage(), lev.getLev(), mplTemp['c'], mplTemp['f'])
            myAWSIoTMQTTClient.publish("topic/devices/data", JSONpayload, 0)
            print("Published Message: " + JSONpayload)
            cycleCnt = cycleCnt + 1
            
            time.sleep(5)
            print("Going to Sleep for %s seconds"%(str(sleepTime)))
            
            ### Disconnect from the Network
            res = cloud.network.disconnect()
            if res:
                print('PPP session ended')
            else:
                print('Failed to end PPP session')
                print("ERROR 109: Unable to Connect Modem; ")
            
            ### Bash Command to Enter Sleep Cycle
            bashCommand = "sudo rtcwake -u -s " + (sleepTime) + " -m standby"
            print("@bash: sudo rtcwake -u -s " + (sleepTime) + " -m standby")
            process = subprocess.Popen(bashCommand.split(), stdout=subprocess.PIPE)
            output, error = process.communicate()
    
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