Logi v1.0

### Program Structure ###

logi-1 - program folder

    -> controls - contains scripts for all input/output peripherals used by Logi
        -> AD8.py   - thermocouple class
        -> LED.py   - LED class
        -> MPL.py   - barometric class
        -> MQTT.py  - AWS MQTT connection class
        -> PX3.py   - pressure sensor class

    -> tests - contains tests and experimentation based scripts

    -> run - Logi's main running scripts
        -> cell_connect.py  - cellular connection script
        -> wifi_connect.py  - wifi connection script
        -> LogiConnect.py   - LOGI Connection Class 
        -> MQTTConnect.py   - MQTT Connection Class

### MQTT Keys ###

keys - contains device specific information for AWS MQTT broker connection

    -> root-CA.crt          - AWS root-CA file
    -> Logi#.cert.pem       - AWS device certificate
    -> Logi#.private.key    - AWS private key
    -> Logi#.public.key     - AWS public key   
    -> schedule.txt         - device publishing scheduled time 
    -> serial.txt           - device serial number
    -> thingName.txt        - device name

### How To Run ###

### Error List ###

    ERR101 - Modem USB connection error. Unable to connect to the USB modem - modem and/or USB port are not active.
    ERR103 - Modem serial connection error. Unable to connect to the USB modem - modem or USB serial port is busy and unable to communicate.
    ERR105 - Cellular network connection error. Unable to start a new PPP session. Other PPP sessions currently active. 
    ERR107 - Cellular network connection error. Unable to start a new PPP session. Cell network does not recognize the sim. 
    ERR109 - Temporary failure in DNS server name resolution. Unable to connect to the MQTT broker. The MQTT broker may have timed out the access tokens.
    ERR111 - Unable to connnect to the MQTT broker.
    ERR113 - MQTT parameter initialization error. Unable to find the private authentication keys to connect to MQTT broker.
    ERR115 - I/O initialization error. Unable to initialize I/O signals.
    ERR117 - RSSI value error. Unable to acquire RSSI value.
    ERR119 - I2C signal error. I2C input signals are either faulted or not detected.
    ERR121 - MQTT Connection Timeout
    ERR123 - Modem reports readiness but returns no data
    ERR125 - SSL Cerficate Verification Error, certificate not yet valid
    ERR127 - Publish Timeout Exception
    ERR129 - Cloud object error
    ERR131 - Cellular connection error
    ERR133 - Failed to kill pid processes
    ERR135 - NTP server error
    ERR137 - Process kill failure; no such process
    ERR139 - MQTT Publish Error
    ERR141 - Unable to Publish to MQTT, publish cycle skipped
    ERR143 - Battery status GPIO error
