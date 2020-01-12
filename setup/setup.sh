#!/bin/bash
echo -e 
apt-get update 
apt-get remove python3
rm -r /usr/bin/python3*
rm -r /usr/local/lib/python3*
rm -r /usr/lib/python3*
apt install build-essential zlib1g-dev libncurses5-dev libgdbm-dev libnss3-dev libssl-dev libreadline-dev libffi-dev wget
cd /home/debian
curl -O https://www.python.org/ftp/python/3.7.3/Python-3.7.3.tar.xz
tar -xf Python-3.7.3.tar.xz
rm -f Python-3.7.3.tar.xz
cd Python-3.7.3
./configure
make
make install
python3 -m pip install smbus serial pyserial Adafruit_BBIO AWSIoTPythonSDK xmodem ntplib datetime
python3 -m pip install hologram-python
apt-get install ntp
