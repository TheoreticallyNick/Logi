
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
from serial.tools import list_ports

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

def main():

    clean_kill()

    device_names = []
    usb_ids = [('05c6', '90b2')]

    for usb_id in usb_ids:
        vid = usb_id[0]
        pid = usb_id[1]

        # The list_ports function returns devices in descending order, so reverse
        # the order here to iterate in ascending order (e.g. from /dev/xx0 to /dev/xx6)
        # since our usable serial devices usually start at 0.
        udevices = [x for x in list_ports.grep("{0}:{1}".format(vid, pid))]
        print(udevices)
        for udevice in reversed(udevices):
            print('checking port %s'%(udevice.name))

    ### Init Cloud Object
    print('Connecting to on-board modem and building new cloud object...')
    cloud = CustomCloud(None, network='cellular')
    print('--> Successfully found USB Modem')

    ### Connect to Cellular Network
    print('Connecting to Cellular Network...')
    connect_result = cloud.network.connect()
    print('Result' + str(connect_result))

if __name__=="__main__":
    main()