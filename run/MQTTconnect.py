class ConnectMQTTParams:

    def __init__(self):
        
        name_file = open("/home/debian/Desktop/keys/thingName.txt", "r")
        self.name = name_file.readline()
        serial_file = open("/home/debian/Desktop/keys/serial.txt", "r")
        self.serial = serial_file.readline()
        self.thingName = self.name
        self.mqttClientId = self.name
        self.serial = self.serial
        self.host = "a28v8anidrrkyj-ats.iot.us-east-2.amazonaws.com"
        self.rootCAPath = "/home/debian/Desktop/keys/root-CA.crt"
        self.certificatePath = "/home/debian/Desktop/keys/" + self.name + ".cert.pem"
        self.privateKeyPath = "/home/debian/Desktop/keys/" + self.name + ".private.key"
        self.port = 8883
        

class CallbackContainer(object):

    def __init__(self, client):
        self._client = client

    def messagePrint(self, client, userdata, message):
        print("Received a new message: ")
        print(message.payload)
        print("from topic: ")
        print(message.topic)
        print("--------------\n\n")



