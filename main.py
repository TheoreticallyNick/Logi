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

def lightLoop(lightObj):
    t = threading.currentThread()
    while getattr(t, "do_run", True):
        lightObj.lightHeart()

def main():
        
    led_red = CommandLED("P8_8")
    led_red.lightOn()

    print("###---------- Logi 2.1 Program Start ----------###")
    sleepTime = (input("Sleep Time in Hours: "))

    cycleCnt = 1

    while True:
        
        if cycleCnt != 1:
            print("Waking up Logi...")
        
        time.sleep(20)
        led_red = CommandLED("P8_8")
        led_red.lightOn()
        
        err = ""
        
        print("Connecting to Cellular Network...")
        
        try:
            connectCommand = "sudo hologram network connect -vv"
            print("@bash: sudo hologram network connect -vv")
            process = subprocess.Popen(connectCommand.split(), stdout=subprocess.PIPE)
            time.sleep(20)
            print("Cellular Network Connection Successful -- PPP Session Started")
        except:
            output, error = process.communicate()
            print("ERROR 109: Unable to Connect Modem; ")
    
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
        try:    
            myAWSIoTMQTTClient.connect()
            print("--> Successfully Connected")
        except: 
            print("ERROR 105: Error connecting to MQTT Client")
            err = Err + "ERROR 105: Error connecting to MQTT Client; "
    
        ### Start connection light heartbeat
        LED_blu_t = threading.Thread(name='lightLoop', target=lightLoop, args=(led_blu,))
        LED_blu_t.start()
    
        #myAWSIoTMQTTClient.subscribe("topic/devices/cast", 0, myCallbackContainer.messagePrint)
        
        #mqtt_time = int(input("MQTT Frequency: "))
        
        
        #print("Publishing in...")
        #count_down = 3
        #while (count_down >= 0):
            #if count_down != 0:
                #print(count_down)
                #count_down = count_down - 1
                #time.sleep(1)
            #else:
                #print("Publishing...")
                #break
        
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
    
            JSONpayload = '{"id": "%s", "ts": "%s", "ts_l": "%s", "schema": "mqtt_v1", "cycle": "%s", "error": "%s", "DS1318_volts": %.2f, "Fluid_per": %.2f, "MPL_c": %.2f, "MPL_f": %.2f}'%(mqtt.thingName, timestamp, timelocal, str(cycleCnt), err, lev.getVoltage(), lev.getLev(), mplTemp['c'], mplTemp['f'])
            myAWSIoTMQTTClient.publish("topic/devices/data", JSONpayload, 0)
            print("Published Message: " + JSONpayload)
            cycleCnt = cycleCnt + 1
            
            time.sleep(5)
            print("Going to Sleep for %s hours"%(str(sleepTime)))
            
            try:
                disconnectCommand = "sudo hologram network disconnect -vv"
                print("@bash: sudo hologram network disconnect -vv")
                process = subprocess.Popen(disconnectCommand.split(), stdout=subprocess.PIPE)
                time.sleep(20)
                print("Cellular Network Disconnected Successfully")
            
            except:
                print("ERROR 111: Unable to Disconnect Modem; ")
                output, error = process.communicate()
            
            
            bashCommand = "sudo rtcwake -u -s " + (sleepTime) + " -m standby"
            print("@bash: sudo rtcwake -u -s " + (sleepTime) + " -m standby")
            process = subprocess.Popen(bashCommand.split(), stdout=subprocess.PIPE)
            output, error = process.communicate()
    
        except KeyboardInterrupt:
            pass
            
    LED_blu_t.do_run = False
    LED_blu_t.join()
    led_red.lightOff()
    led_red.lightOff()
    
    GPIO.cleanup()
    print("\n Program Terminated")

    os._exit(1)

if __name__=="__main__":
    main()