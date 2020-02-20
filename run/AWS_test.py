import time
from AWSIoTPythonSDK.MQTTLib import AWSIoTMQTTClient
from AWSIoTPythonSDK.exception.AWSIoTExceptions import *
import json
import random

class ConnectMQTTParams:

    def __init__(self):

        self.host = "a28v8anidrrkyj-ats.iot.us-east-2.amazonaws.com" #insert host address
        self.rootCAPath = "/home/debian/Desktop/Detroit-Meats/AmazonRootCA1.pem" #insert root-ca.crt file path
        self.certificatePath = "/home/debian/Desktop/Detroit-Meats/Detroit_Meats.cert.pem" #insert cert.pem file path
        self.privateKeyPath = "/home/debian/Desktop/Detroit-Meats/Detroit_Meats.private.key" #insert private.key file path
        self.port = 8883
        self.thingName = "Detroit_Meats" #insert thing name
        self.mqttClientId = "Detroit_Meats" #insert mqttClientId

mqtt = ConnectMQTTParams()

### Initializes all parameters and keys for the MQTT broker connection
myAWSIoTMQTTClient = None

myAWSIoTMQTTClient = AWSIoTMQTTClient(mqtt.mqttClientId)
myAWSIoTMQTTClient.configureEndpoint(mqtt.host, mqtt.port)
myAWSIoTMQTTClient.configureCredentials(mqtt.rootCAPath, mqtt.privateKeyPath, mqtt.certificatePath)
myAWSIoTMQTTClient.configureAutoReconnectBackoffTime(1, 32, 20)
myAWSIoTMQTTClient.configureConnectDisconnectTimeout(10)  # 10 sec
myAWSIoTMQTTClient.configureMQTTOperationTimeout(5)  # 5 sec
print('--> Successfully Initialized AWS MQTT!')

mqtt_result = myAWSIoTMQTTClient.connect()

random.seed()

while True: 

    timestamp = time.time()
    timelocal = time.strftime('%Y-%m-%d %H:%M:%S %Z', time.localtime())

    ### Set the MQTT Message Payload
    JSONpayload = json.dumps(
        {'id': mqtt.thingName, 'ts': timestamp, 'ts_l': timelocal, 
        'data': random.random()})

    ### Publish JSON to MQTT Topic
    topic = 'topic/detroitmeats'
    myAWSIoTMQTTClient.publishAsync(topic, JSONpayload, 1) 
    print('Topic: topic/devices')
    print('Published Message: ' + JSONpayload)

    time.sleep(15)