FROM debian:buster
FROM python:3.7

ADD logi_cellular.py /

RUN pip3 install hologram-python && \
    pip3 install smbus && \
    pip3 install serial && \
    pip3 install AWSIoTPythonSDK

CMD [ "python", "logi_cellular.py" ]
