Logi v1.0

### Program Structure ###

logi-1 - program folder
    -> controls - contains scripts for all input/output peripherals used by Logi
        -> AD8.py   - thermocouple class
        -> LED.py   - LED class
        -> MPL.py   - barometric class
        -> MQTT.py  - AWS MQTT connection class
        -> PX3.py   - pressure sensor class
    
    -> resources - contains necessary SDK's for Logi program function

    -> tests - contains tests and experimentation based scripts

    -> main.py - Logi's main program script

### MQTT Keys

keys - contains device specific information for AWS MQTT broker connection
    -> MQTTconnect.py   - device birth certificate
    -> root-CA.crt      - AWS root-CA file
    -> Bone#.cert.pem    - AWS device certificate
    -> Bone#.private.key - AWS private key
    -> Bone#.public.key  - AWS public key    

### How To Run ###
