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
from AWSIoTPythonSDK.exception.AWSIoTExceptions import connectTimeoutException
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

def clean_kill():
    ### Turns off and destroys all PPP sessions to the cellular network
    logging.info('Disconnecting All Sessions...')

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

def rtc_wake(rolex, mode):
    
    logging.warning('Soft Rebooting...')
    bashCommand = "sudo rtcwake -u -s %s -m %s"%(rolex, mode)
    logging.info("@bash: %s", bashCommand)
    process = subprocess.Popen(bashCommand.split(), stdout=subprocess.PIPE)
    output, error = process.communicate()

    time.sleep(15)

def antenna_cycle(cloud):
    
    logging.info('Cycling the radio antenna...')
    cloud.network.modem.radio_power(False)
    time.sleep(5)
    cloud.network.modem.radio_power(True)
    time.sleep(5)

def connect_cycle():
    attempts = 1
    err = ""

    while attempts <= 4:

        if attempts == 4:
            sleep_time = sleep_calc(wake_time)
            logging.critical('FATAL ERROR: %s', err)
            logging.critical('3 attempts made to connect to connect to mqtt client')
            logging.critical('Sleeping until next cycle...')
            logging.info('Wake up time: %s', wake_time)
            rtc_wake(str(sleep_time), "mem")
            attempts = 1
            continue

        cloud = None
        logging.info('- Connection Cycle Attempt %i -', attempts)

        try:
            clean_kill()

            ### Init Cloud Object
            logging.info('Connecting to on-board modem and building new cloud object...')
            cloud = CustomCloud(None, network='cellular')
            logging.info('--> Successfully found USB Modem') 

            ### Cycle the Antenna
            antenna_cycle(cloud)
            
            ### Connect to Cellular Network
            logging.info('Connecting to Cellular Network...')
            connect_result = cloud.network.connect()
            if connect_result == False:
                logging.error('ERR107: Could not connect to cellular network - modem hangup')
                err = err + "E107; "
                attempts += 1
                clean_kill()
                rtc_wake("15", "mem")
                continue
            else:
                logging.info('--> Successfully Connected to Cell Network')

            time.sleep(10)

            ### Connect to MQTT Client
            logging.info('Connecting to MQTT...')
            mqtt_result = myAWSIoTMQTTClient.connect()
            if mqtt_result == False: 
                logging.error('ERR111: Could not Connect to MQTT Client')
                err = err + "E111; "
                attempts += 1
                clean_kill()
                rtc_wake("15", "mem")
                continue
            else: 
                logging.info('--> Successfully Connected to MQTT Client')

            time.sleep(10)
            
            break

        ### Cloud Object Error
        except NetworkError:
            logging.error('ERR101: Could not find modem')
            err = err + "E101; "
            clean_kill()
            rtc_wake("15", "mem")
            attempts += 1
            continue

        ### Cloud Object Error
        except SerialError:
            logging.error('ERR103: Could not find usable serial port')
            err = err + "E103; "
            clean_kill()
            rtc_wake("15", "mem")
            attempts += 1
            continue
        
        ### Cellular Connection Error
        except PPPError:
            logging.error('ERR105: Could not start a PPP Session -- Other Sessions still open')
            err = err + "E105; "
            clean_kill()
            rtc_wake("15", "mem")
            attempts += 1
            continue

        ### Cellular Connection Error    
        except SerialException:
            logging.error('ERR123: Modem reports readiness but returns no data')
            err = err + "E123; "
            clean_kill()
            rtc_wake("15", "mem")
            attempts += 1
            continue

        ### DNS Server Connection Error
        except gaierror:
            logging.error('ERR109: Temporary failure in DNS server name resolution')
            err = err + "E109; "
            clean_kill()
            rtc_wake("15", "mem")
            attempts += 1
            continue
        
        ### MQTT Connection Error
        except connectTimeoutException:
            logging.error('ERR121: MQTT client connection timeout')
            err = err + "E121; "
            clean_kill()
            rtc_wake("15", "mem")
            attempts += 1
            continue
        
        ### MQTT Connection Error
        except SSLCertVerificationError:
            logging.error('ERR125: SSL Cerficate Verification Error, certificate not yet valid')
            err = err + "E125; "
            clean_kill()
            rtc_wake("15", "mem")
            attempts += 1

        ### Clean Kill Error
        except NoSuchProcess:
            pass

    return cloud, err

def get_ntp(server):
    
    hostname = "google.com"
    response = os.system("ping -c 1 " + hostname)
    try:
        ntpDate = None
        client = ntplib.NTPClient()
        response = client.request(server, version=3)
        response.offset
        ntpDate = ctime(response.tx_time)
        logging.info('UTC Server Time is: %s', ntpDate)
    
    except Exception as e:
        print(e)
    
    return ntpDate

def set_time(rolex):

    logging.warning('Setting HWclock...')
    bashCommand = 'hwclock --set --date %s'%(rolex)
    logging.info("@bash: %s", bashCommand)
    process = subprocess.Popen(bashCommand.split(), stdout=subprocess.PIPE)
    output, error = process.communicate()

    time.sleep(3)

    logging.warning('Setting System Clock to HWclock...')
    bashCommand = 'hwclock --hctosys'
    logging.info("@bash: %s", bashCommand)
    process = subprocess.Popen(bashCommand.split(), stdout=subprocess.PIPE)
    output, error = process.communicate()

    time.sleep(3)

def main():

    global schema
    global wake_time
    global myAWSIoTMQTTClient
    
    ### Set timezone
    timelocal = time.strftime("%Y-%m-%d %H:%M:%S %Z", time.localtime())

    ### Set up the logger
    logi_log = "logi_log.log"
    logging.basicConfig(filename=logi_log, filemode='w', format='%(asctime)s -- %(levelname)s: %(message)s', level=logging.INFO)
    console = logging.StreamHandler()
    console.setLevel(logging.INFO)
    logging.getLogger('').addHandler(console)

    ### Start the program
    logging.info('###---------- Logi Cellular Program Start ----------###')

    ### Set sleep schedule
    sched = []      # empty schedule list

    f = open('/home/debian/Desktop/keys/schedule.txt', 'r')
    sched = f.read().split(',')
    f.close()

    logging.info(sched)       

    sched_cycle = cycle(sched)
    wake_time = sched[0]

    ### Init MQTT Parameters
    logging.info('Initializing MQTT Connection Parameters...')
    mqtt = ConnectMQTTParams()
    myAWSIoTMQTTClient = init_mqtt(mqtt)

    ### Schema Version
    schema = 'schema_1_2'
    logging.info('MQTT Schema: %s', schema) 

    cycleCnt = 1
            
    while True:

        try:
            ### Start cycle
            logging.info('###---------- Starting Cycle Number: %i ----------###', cycleCnt)
            led_red = CommandLED("P8_8")
            led_red.lightOn()
            
            ### Start Connection Process
            cloud, err = connect_cycle()

            ### Calibrate the System Time
            if cycleCnt == 1:
                rolex = get_ntp('0.debian.pool.ntp.org')
                logging.info('UTC Time: %s', rolex)
                set_time(rolex)

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

            ### Next Wake Up Time
            wake_time = (next(sched_cycle))

            ### Set the MQTT Message Payload
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

            ### Set Subscribe Time Window Here
            
            ### Kill all open PPP connections and processes
            logging.info('Killing all PPP connections...')
            clean_kill()
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
