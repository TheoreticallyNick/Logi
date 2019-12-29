FROM balenalib/beaglebone-black:stretch
FROM python:3.7

ADD logi_test.py /

RUN apt-get update && apt-get install -y \
    python-dev \
    python-pip

RUN pip install hologram-python \
    smbus \
    serial \ 
    AWSIoTPythonSDK==1.0.0 \
    Adafruit_BBIO 

CMD [ "python", "./logi_test.py" ]
