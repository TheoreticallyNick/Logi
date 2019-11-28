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

    while attempts < 5:
        cloud = None
        print("- Modem Connection Attempt %i -"%(attempts))
        time.sleep(10)
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

    while attempts < 4:
        print("- Cellular Network Connection Attempt %i -"%(attempts))
        result = cloud.network.connect()
        '''try:
            result = cloud.network.connect()
        except PPPError:
            print("ERR10X: Existing PPP sessions ongoing")
            err = err + "ERR10X; "
            attempts += 1
            cleanKill(cloud)
            continue'''

        if result == True:
            print("--> Successfully Connected to Cell Network")
            break
        else:
            print("ERR105: Could not create a new PPP Session")
            err = err + "ERR105; "
            attempts += 1
            cloud.network.disconnect()
            print("Turning Off Radio...")
            cloud.network.modem.radio_power(False)
            time.sleep(10)
            print("Turning On Radio...")
            cloud.network.modem.radio_power(True)
            time.sleep(10)

    if attempts >= 3:
        sys.exit("FATAL ERROR: " + err) 

def connectMQTT(client):
    ### Redundancy for Connecting to MQTT Client ###
    print("Connecting to MQTT...")
    attempts = 1
    err = ""

    while attempts < 4:
        print("- MQTT Client Connection Attempt %i -"%(attempts))
        time.sleep(10)
        try:
            result = client.connect()
        except gaierror:
            print("ERR111: Failure in DNS Server Name Resolution")
        
        if result == True:
            print("--> Successfully Connected to MQTT Client")
            break
        else:
            print("ERR107: Could not Connect to MQTT Client")
            err = err + "ERR107; "
            attempts += 1

    if attempts >= 3:
        print("FATAL ERROR: " + err)
        os._exit(1)  

def initMQTTClient(mqtt):
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
        print("ERR109: Error Initializing MQTT Connection Parameters -- Check your Keys")
        os._exit(1)
    
    return myAWSIoTMQTTClient

def cleanKill(cloud):

    cloud.network.disconnect()
    time.sleep(10)
    cloud.network.modem.radio_power(False)
    time.sleep(10)
    cloud.network.modem.reset()
    time.sleep(10)

    for proc in psutil.process_iter():

        try:
            pinfo = proc.as_dict(attrs=['pid', 'name'])
            print(pinfo)
        except:
            raise HologramError('Failed to check for existing PPP sessions')

        if 'pppd' in pinfo['name']:
            print('Found existing PPP session on pid: %s' % pinfo['pid'])
            print('Killing pid %s now' % pinfo['pid'])
            psutil.Process(pinfo['pid']).kill()
            time.sleep(10)
            psutil.Process(pinfo['pid']).terminate()
            time.sleep(10)
            os.kill(pinfo['pid'], signal.SIGTERM)
            time.sleep(10)
            print(kill_proc_tree(pinfo['pid']))

    for proc in psutil.process_iter():
        pinfo2 = proc.as_dict(attrs=['pid', 'name'])
        print(pinfo2)
    
    time.sleep(5)

def kill_proc_tree(pid, sig=signal.SIGTERM, include_parent=True,
                   timeout=None, on_terminate=None):
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
    gone, alive = psutil.wait_procs(children, timeout=timeout,
                                    callback=on_terminate)
    return (gone, alive)

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
            
            if cycleCnt != 1:    
                time.sleep(900)
            err = ""

            ### Init Cloud Object
            cloud = buildCloudObject()

            ### Connect to Cellular Network
            connectToCellular(cloud)

            ### Connect to MQTT Client
            connectMQTT(myAWSIoTMQTTClient)

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
                print("ERROR 103: Error Initializing Board I/O; ")
                err = err + "ERROR 103; "

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
            
            print("Killing all PPP connections...")
            cleanKill(cloud)
            cloud = None
            time.sleep(15)
            
            ### Bash Command to Enter Sleep Cycle
            #print("Going to Sleep for %s seconds"%(str(sleepTime)))
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