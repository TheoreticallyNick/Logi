#!/bin/bash
import sys, os, signal
sys.path.append('/home/debian/Desktop/Logi/controls/')
sys.path.append('/home/debian/Desktop/keys/')
import threading
import json
import time
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
import AWSIoTPythonSDK.MQTTLib
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

### LogiConnect v1.5 ###
 
class LogiConnect:

    def __init__(self):
        '''
        LogiConnect Constructor
        '''
        self.mqtt = ConnectMQTTParams()
        self.set_logger()
        self.schema = '1.4'
        self.err = ''
        self.cycle_cnt = 1
        self.version = '1.4'
        self.schedule = self.get_schedule()
        self.wake_time = self.get_wake_time()
        self.set_board_io()
        self.mpl = MPL3115A2()
        self.lvl = FluidLevel('P9_39')
        self.bat = Battery('P9_37')

    def get_ping(self):
        '''
        Function: pings the google server
        '''

        hostname = 'google.com'
        response = os.system('ping -c 1 ' + hostname)
        logging.info('Ping Response -> %s', response)

    def time_split(self, time_str):
        '''
        Function: splits the time string into hour and minute integers
        '''
        
        hr = int(time_str[0:2])
        mn = int(time_str[2:])
        
        return hr, mn

    def sleep_calc(self, time_str):
        '''
        Function: calculates the sleeping time in seconds between now and next scheduled wake up
        '''
        
        hr, mn = self.time_split(time_str)

        now = datetime.today()

        if now < now.replace(day=now.day, hour=hr, minute=mn, second=0, microsecond=0):
            nxt = now.replace(day=now.day, hour=hr, minute=mn, second=0, microsecond=0)
        else:
            nxt = now.replace(day=now.day, hour=hr, minute=mn, second=0, microsecond=0) + timedelta(days=1)
        
        dt = nxt - now
        sec = int(dt.total_seconds())

        return sec

    def init_mqtt(self, mqtt):
        '''
        Function: initializes the MQTT parameters
        '''
        
        ### Initializes all parameters and keys for the MQTT broker connection
        self.myAWSIoTMQTTClient = None

        try:
            self.myAWSIoTMQTTClient = AWSIoTMQTTClient(mqtt.mqttClientId)
            self.myAWSIoTMQTTClient.configureEndpoint(mqtt.host, mqtt.port)
            self.myAWSIoTMQTTClient.configureCredentials(mqtt.rootCAPath, mqtt.privateKeyPath, mqtt.certificatePath)
            self.myAWSIoTMQTTClient.configureAutoReconnectBackoffTime(1, 32, 20)
            self.myAWSIoTMQTTClient.configureConnectDisconnectTimeout(10)  # 10 sec
            self.myAWSIoTMQTTClient.configureMQTTOperationTimeout(5)  # 5 sec
            self.myCallbackContainer = CallbackContainer(self.myAWSIoTMQTTClient)
            self.myAWSIoTMQTTClient.configureOfflinePublishQueueing(3, AWSIoTPythonSDK.MQTTLib.DROP_OLDEST)
            logging.info('--> Successfully Initialized!')

        except:
            logging.error('ERR113: Error Initializing MQTT Connection Parameters')
            os._exit(1)
        
        return self.myAWSIoTMQTTClient, self.myCallbackContainer

    def clean_kill(self):
        '''
        Function: Turns off and destroys all PPP sessions to the cellular network
        '''
        logging.info('Disconnecting All Sessions...')

        for proc in psutil.process_iter():

            try:
                pinfo = proc.as_dict(attrs=['pid', 'name'])

                if 'pppd' in pinfo['name']:
                    logging.info('Found existing PPP session on pid: %s', pinfo['pid'])
                    logging.info('Killing pid %s now', pinfo['pid'])
                    psutil.Process(pinfo['pid']).kill()
                    self.kill_proc_tree(pinfo['pid'])

            except Exception as e:
                logging.error('ERR133: Failed to kill pid processes')
                self.err = self.err + 'E133; '
                raise
            
    def kill_proc_tree(self, pid, sig=signal.SIGTERM, include_parent=True, timeout=None, on_terminate=None):
        '''
        Function: kills an entire process tree (including grandchildren) with signal 'sig' and return a (gone, still_alive) tuple.
        'on_terminate', if specified, is a callabck function which is called as soon as a child terminates.
        '''

        assert pid != os.getpid(), 'wont kill myself'
        
        try:
            parent = psutil.Process(pid)
            children = parent.children(recursive=True)
            
            if include_parent:
                children.append(parent)
            
            for p in children:
                p.send_signal(sig)
            
            gone, alive = psutil.wait_procs(children, timeout=timeout, callback=on_terminate)
        
        except: 
            logging.error('ERR137: Process kill failure; no such process')
            self.err = self.err + 'E137; '
            raise
        
        return (gone, alive)

    def rtc_wake(self, rolex, mode):
        '''
        Function: puts the device in sleep mode for defined period of time
        '''
        
        logging.warning('Soft Rebooting...')
        bashCommand = 'sudo rtcwake -u -s %s -m %s'%(rolex, mode)
        logging.info('@bash: %s', bashCommand)
        proc = subprocess.Popen(bashCommand.split(), stdout=subprocess.PIPE)
        proc.communicate()
        proc.stdout.close()
        time.sleep(10)

    def antenna_cycle(self, cloud):
        '''
        Function: cycles the antenna on/off and increases connection reliability
        '''        
        logging.info('Cycling the radio antenna...')
        cloud.network.modem.radio_power(False)
        time.sleep(10)

        cloud.network.modem.radio_power(True)
        time.sleep(10)
    
    def get_ntp(self, server):
        '''
        Function: returns time based on the NTP server
        '''

        try:
            ntpDate = None
            client = ntplib.NTPClient()
            response = client.request(server, version=3)
            response.offset
            ntpDate = time.ctime(response.tx_time)
            logging.info('UTC Server Time is: %s', ntpDate)
        
        except:
            logging.error('ERR135: NTP server error')
            self.err = self.err + 'E135; '
            raise

        return ntpDate

    def set_time(self, rolex):
        '''
        Function: sets the hwclock and sysclock based on ntp time, avoids SSL certificate errors
        '''

        logging.warning('Setting HWclock...')
        bashCommand = 'hwclock --set --date "%s"'%(rolex)
        logging.info('@bash: %s', bashCommand)
        subprocess.call(bashCommand, shell=True)

        time.sleep(3)

        logging.warning('Setting System Clock to HWclock...')
        bashCommand = 'hwclock --hctosys'
        logging.info('@bash: %s', bashCommand)
        subprocess.call(bashCommand, shell=True)

        time.sleep(3)

    def time_now_str(self):
        '''
        Function: converts the time now into a string
        '''

        now = datetime.now()
        hr_now = str(now.hour)
        if len(hr_now) < 2:
            hr_now = '0' + hr_now

        min_now = str(now.minute)
        if len(min_now) < 2:
            min_now = '0' + min_now

        time_now = hr_now + min_now

        return time_now

    def sched_index(self, sched):
        '''
        Function: sets the schedule index to the next scheduled time (instead of starting from index 0)
        '''

        now = self.time_now_str()
        post = []
        pre = []

        for i in range(len(sched)):
            if sched[i] <= now:
                pre.append(sched[i])
            
            if sched[i] > now:
                post.append(sched[i])
        
        pre.sort()
        post.sort()
        new_sched = post + pre
        
        return new_sched

    def publish_mqtt(self, JSONpayload, myAWSIoTMQTTClient):
        '''
        Function: handles publishing message to MQTT broker
        '''
        try:
            topic = 'logi_1_4/devices/%s'%(self.mqtt.thingName)
            logging.info('Topic: %s', topic)
            logging.info('Published Message: %s', JSONpayload)
            myAWSIoTMQTTClient.publish(topic, JSONpayload, 1)    

        except publishTimeoutException:
            logging.error('ERR127: Publish Timeout Exception')
            self.err = self.err + 'E127; '
            raise

        except:
            logging.error('ERR139: MQTT publish error')
            self.err = self.err + 'E139; '
            raise

    def create_cloud(self):
        '''
        Function: initializes cloud object
        '''
        logging.info('Connecting to on-board modem and building new cloud object...')
        try:
            cloud = CustomCloud(None, network='cellular')

        except NetworkError:
            logging.error('ERR101: Could not find modem')
            self.err = self.err + 'E101; '
            raise 

        except SerialError:
            logging.error('ERR103: Could not find usable serial port')
            self.err = self.err + 'E103; '
            raise
        
        except:
            logging.error('ERR129: Cloud object error')
            self.err = self.err + 'E129; '
            raise
        
        else: 
            logging.info('--> Successfully found USB Modem & created cloud object') 
            return cloud
             
    def cell_connect(self, cloud):
        '''
        Function: connects device to cell tower and starts ppp session
        '''
        logging.info('Connecting to Cellular Network...')
        try:
            connect_result = cloud.network.connect()

        except PPPError:
            logging.error('ERR105: Could not start a PPP Session -- Other Sessions still open')
            self.err = self.err + 'E105; '
            raise
  
        except SerialException:
            logging.error('ERR123: Modem reports readiness but returns no data')
            self.err = self.err + 'E123; '
            raise

        except:
            logging.error('ERR131: Cellular connection error')
            self.err = self.err + 'E131; '
            raise

        else:
            if connect_result == False:
                logging.error('ERR107: Could not connect to cellular network - modem hangup')
                self.err = self.err + 'E107; '
                raise Exception(ConnectionError)
            else:
                logging.info('--> Successfully Connected to Cell Network')
                time.sleep(5)

    def mqtt_connect(self, myAWSIoTMQTTClient):
        '''
        Function: connect to MQTT broker
        '''
        logging.info('Connecting to MQTT...')
        try:
            mqtt_result = myAWSIoTMQTTClient.connect()

        except gaierror:
            logging.error('ERR109: Temporary failure in DNS server name resolution')
            self.err = self.err + 'E109; '
            raise

        except connectTimeoutException:
            logging.error('ERR121: MQTT client connection timeout')
            self.err = self.err + 'E121; '
            raise

        except SSLCertVerificationError:
            logging.error('ERR125: SSL Cerficate Verification Error, certificate not yet valid')
            self.err = self.err + 'E125; '
            raise

        else:
            if mqtt_result == False: 
                logging.error('ERR111: Could not Connect to MQTT Client')
                self.err = self.err + 'E111; '
                raise Exception(connectError)

            else: 
                logging.info('--> Successfully Connected to MQTT Client')
                time.sleep(10)
        
    def skip_cycle(self):
        '''
        Function: skips mqtt publish and enters sleep cycle
        '''

        self.wake_time = (next(self.schedule))
        sleep_time = self.sleep_calc(self.wake_time)
        logging.critical('FATAL ERROR: %s', self.err)
        logging.critical('3 attempts made to connect to connect to mqtt client')
        logging.critical('Sleeping until next cycle...')
        logging.info('Wake up time: %s', self.wake_time)
        self.rtc_wake(str(sleep_time), 'mem')
    
    def time_fetch(self):
        '''
        Function: fetches time from NTP servers
        '''
        logging.info('Calibrating system clock...')
        rolex = self.get_ntp('1.debian.pool.ntp.org')
        logging.info('UTC Time: %s', rolex)
        return rolex
        
    def set_logger(self):
        '''
        Function: sets up the logger
        '''
        logi_log = self.mqtt.thingName + '_log.log'
        logging.basicConfig(filename=logi_log, filemode='w', format='%(asctime)s -- %(levelname)s: %(message)s', level=logging.INFO)
        console = logging.StreamHandler()
        console.setLevel(logging.INFO)
        logging.getLogger('').addHandler(console)
        logging.info('--> Logger Successfully Initialized')
    
    def get_schedule(self):
        '''
        Function: retrieves the schedule from schedule.txt file
        '''
        sched = [] 
        f = open('/home/debian/Desktop/keys/schedule.txt', 'r')
        sched = cycle(self.sched_index(f.read().split(','))) 
        f.close()

        return sched

    def get_wake_time(self):
        '''
        Function: sets the wake time variable
        '''
        wake = (next(self.schedule))
        return wake
    
    def set_board_io(self):
        '''
        Function: initializes the I/O
        '''
        logging.info('Initialing Board I/O...')
        try:    
            ADC.setup()
            logging.info('--> Successfully Initialized I/O')
        except:
            logging.error('ERR115: Error initializing board I/O')
            self.err = self.err + 'E115; '
            raise

    def custom_callback(self, client, userdata, message):
        logging.info("Received a new message: " + message.payload)
        logging.info("from topic: " + message.topic)
    
    def get_payload(self):

        payload = json.dumps(
            {'id': self.mqtt.thingName, 'serial': self.mqtt.serial, 'ts': int(time.time()), 'ts_l': self.local_time(), 
            'schem': self.schema, 'ver': self.version, 'wake': self.wake_time, 'cyc': self.cycle_cnt, 'err': self.err, 
            'rssi': self.get_rssi(), 'bat': self.bat.get_voltage(), 'lvl': self.lvl.get_lvl(), 'temp': int(self.mpl.get_tempf())})

        return payload
    
    def local_time(self):
        time_local = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime())

        return time_local
    
    def get_rssi(self):
        try: 
            rssi = str(cloud.network.modem.signal_strength)
        except:
            logging.error('ERR117: Error getting RSSI values')
            rssi = 'err'
            self.err = self.err + 'E117; '

        return rssi
    
    def set_local_time(self, zone):
        os.environ['TZ'] = zone
        time.tzset()
    
