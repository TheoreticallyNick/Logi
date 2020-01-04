Logi v1.0

### Program Structure ###

logi-1 - program folder

    '
    -> controls - contains scripts for all input/output peripherals used by Logi
        -> AD8.py   - thermocouple class
        -> LED.py   - LED class
        -> MPL.py   - barometric class
        -> MQTT.py  - AWS MQTT connection class
        -> PX3.py   - pressure sensor class

    -> tests - contains tests and experimentation based scripts

    -> run - Logi's main running scripts
        -> logi_cellular.py - cellular connection script
        -> logi_wifi.py     - wifi connection script
    '

### MQTT Keys

keys - contains device specific information for AWS MQTT broker connection
    -> MQTTconnect.py   - device birth certificate
    -> root-CA.crt      - AWS root-CA file
    -> Bone#.cert.pem    - AWS device certificate
    -> Bone#.private.key - AWS private key
    -> Bone#.public.key  - AWS public key    

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
    ERR125 - Battery status GPIO error
