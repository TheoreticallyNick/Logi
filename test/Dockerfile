FROM debian:buster
FROM python:3.7

ADD logi_test.py /

RUN pip install hologram-python && \
    pip install smbus && \
    pip install serial && \
    pip install AWSIoTPythonSDK \
    pip install Adafruit_BBIO \

CMD [ "python", "logi_test.py" ]
