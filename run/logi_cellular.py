#!/bin/bash
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

### TODO:
#       - Put together an array of the connection function
#       - Look into using Docker to create the right virtual machine to run this on 
#       - Determine appropriate tunnel time window

class LogiConnect:

    def __init__(self):
        '''
        LogiConnect Constructor
        '''
        self.mqtt = ConnectMQTTParams()
        self.schema = 'schema_1_2'
        self.err = ''
        self.cycle_cnt = 1

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
            ntpDate = ctime(response.tx_time)
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
            topic = 'logi/devices/%s'%(self.mqtt.thingName)
            logging.info('Topic: %s', topic)
            logging.info('Published Message: %s', JSONpayload)
            myAWSIoTMQTTClient.publishAsync(topic, JSONpayload, 1)    

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
                time.sleep(5)
        
    def skip_cycle(self, sched):
        '''
        Function: skips mqtt publish and enters sleep cycle
        '''

        self.wake_time = (next(sched))
        sleep_time = self.sleep_calc(self.wake_time)
        logging.critical('FATAL ERROR: %s', self.err)
        logging.critical('3 attempts made to connect to connect to mqtt client')
        logging.critical('Sleeping until next cycle...')
        logging.info('Wake up time: %s', self.wake_time)
        self.rtc_wake(str(sleep_time), 'mem')

        return sched
    
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
    
    def set_schedule(self):
        '''
        Function: creates schedule array, indexed to the nearest scheduled time
        '''
        sched = [] 
        f = open('/home/debian/Desktop/keys/schedule.txt', 'r')
        sched = f.read().split(',')
        f.close()
        sched = self.sched_index(sched)   
        sched_cycle = cycle(sched)
        wake_time = sched[0]

        return sched_cycle, wake_time

    def set_board_io(self):
        '''
        Function: initializes the I/O
        '''
        logging.info('Initialing Board I/O...')
        try: 
            ADC.setup()
            lev     = FluidLevel('P9_39')
            mpl     = MPL3115A2()
            bat     = Battery('P9_37')
            logging.info('--> Successfully Initialized I/O')
        except:
            logging.error('ERR115: Error initializing board I/O')
            self.err = self.err + 'E115; '
            raise

        return lev, mpl, bat

    def custom_callback(self, client, userdata, message):
        logging.info("Received a new message: " + message.payload)
        logging.info("from topic: " + message.topic)
    
    def main(self):

        ### Set up the logger
        self.set_logger()

        ### Start the program
        logging.info('###---------- Logi Cellular v1.1.5 Program Start ----------###')
        
        myAWSIoTMQTTClient, callBackContainer = self.init_mqtt(self.mqtt)

        ### Schema Version
        logging.info('MQTT Schema: %s', self.schema) 

        ### Connection Cycle
        logging.info('Initial connection and calibration...')
        while True:
            try:
                cloud = self.create_cloud()
                self.antenna_cycle(cloud)
                self.cell_connect(cloud)
                break

            except:
                self.rtc_wake('10', 'mem')
                
                try:
                    self.clean_kill()
                except:
                    pass

                continue
   
        ### Calibrate system clock
        rolex = self.time_fetch()
        self.set_time(rolex)

        ### Set sleep schedule
        sched_cycle, wake_time = self.set_schedule()
        
        ### Init Board I/O
        lev, mpl, bat = self.set_board_io()
                
        ### Publish Program Loop
        while True:

            ### Start cycle
            logging.info('###---------- Starting Cycle Number: %i ----------###', self.cycle_cnt)
            led_red = CommandLED('P8_7')
            led_red.lightOn()
            
            ### Start Connection Process
            att = 1
            while True:

                if att == 4:
                    sched_cycle = self.skip_cycle(sched_cycle)
                    att = 1
                    continue
                
                if self.cycle_cnt != 1: 
                    try:
                        cloud = self.create_cloud()
                        self.antenna_cycle(cloud)
                        self.cell_connect(cloud)
                        self.mqtt_connect(myAWSIoTMQTTClient)
                        break
                    except:
                        logging.info('Connection Cycle unsuccessful, rebooting...')
                        try:
                            self.clean_kill()
                        except:
                            pass
                        att += 1
                        self.rtc_wake('10', 'mem')
                        continue
                
                else:
                    try:
                        self.mqtt_connect(myAWSIoTMQTTClient)
                        break
                    except:
                        logging.info('Connection Cycle unsuccessful, rebooting...')
                        try:
                            self.clean_kill()
                        except:
                            pass
                        att += 1
                        self.rtc_wake('10', 'mem')
                        continue


            ### Record the RSSI
            try: 
                rssi = cloud.network.signal_strength
            except:
                logging.error('ERR117: Error getting RSSI values')
                rssi = 'err'
                self.err = self.err + 'E117; '
        
            ### Subscribe to MQTT Topics
            mstr_topic = 'logi/master/%s'%(self.mqtt.thingName)
            self.myAWSIoTMQTTClient.subscribe(mstr_topic, 0, self.custom_callback)
            
            ### Timestamp 
            timestamp = time.time()
            timelocal = time.strftime('%Y-%m-%d %H:%M:%S %Z', time.localtime())
            
            ### Get Temperature Data from MPL
            try:
                mpl.control_alt_config()
                mpl.data_config()
                mplTemp = mpl.read_alt_temp()
            except:
                logging.error('ERR119: I2C bus error')
                self.err = self.err + 'E119; '
                mplTemp = {'a' : 999, 'c' : 999, 'f' : 999}

            ### Next Wake Up Time
            wake_time = (next(sched_cycle))

            ### Set the MQTT Message Payload
            JSONpayload = json.dumps(
                {'id': self.mqtt.thingName, 'ts': timestamp, 'ts_l': timelocal, 
                'schem': self.schema, 'wake': wake_time, 'cyc': str(self.cycle_cnt), 'err': self.err, 
                'rssi': rssi, 'bat': bat.getVoltage(), 'fuel': lev.getLev(), 'temp': mplTemp['c']})

            ### Publish to MQTT Broker
            att = 1
            while True:
                if att == 4:
                    logging.error('Three MQTT publish attempts failed, publish cycle skipped')
                    break
                try:
                    self.publish_mqtt(JSONpayload, myAWSIoTMQTTClient)
                except:
                    logging.error('ERR141: Unable to Publish to MQTT, publish cycle skipped')
                    self.err = self.err + 'ERR141; '
                    att += 1
                    continue
                finally:
                    self.err = ''
                    break

            self.cycle_cnt = self.cycle_cnt + 1
            
            ### Subscribed time window
            time.sleep(10)
            
            
            ### Kill all open PPP connections and processes
            logging.info('Killing all PPP connections...')
            try:
                self.clean_kill()
            except:
                pass
            
            ### Cycle LED's to OFF
            led_red.lightOff()
            GPIO.cleanup()

            ### Bash Command to Enter Sleep Cycle
            logging.info('Wake up time: %s', wake_time)
            sleep_time = self.sleep_calc(wake_time)
            logging.info('Sleep time in sec: %s', str(sleep_time))
            self.rtc_wake(str(sleep_time), 'mem')
        
if __name__=='__main__':
    logi = LogiConnect()
    logi.main()
