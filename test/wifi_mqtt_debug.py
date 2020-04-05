import os, sys
sys.path.append('/home/debian/Desktop/Logi/run')
from LogiConnect import LogiConnect
import logging
import time

### Create LogiConnect Object
logi = LogiConnect()

logging.info('###---------- Logi Cellular v1.4 Program Start ----------###')

myAWSIoTMQTTClient, callBackContainer = logi.init_mqtt(logi.mqtt)

### Schema Version
logging.info('MQTT Schema: %s', logi.schema) 

### Connection Cycle
logging.info('Initial connection and calibration...')

### Calibrate system clock
logi.set_time(logi.time_fetch())
logi.set_local_time('America/Detroit')

### Publish Program Loop
while True:

    ### Start cycle
    logging.info('###---------- Starting Cycle Number: %i ----------###', logi.cycle_cnt)
    
    ### Start Connection Process
    att = 1
    while True:
        try:
            logi.mqtt_connect(myAWSIoTMQTTClient)
            break
        except:
            logging.info('Connection Cycle unsuccessful, rebooting...')
            try:
                logi.clean_kill()
            except:
                pass
            att += 1
            logi.rtc_wake('10', 'mem')
            continue


    ### Next Wake Up Time
    logi.wake_time = (next(logi.schedule))

    

    ### Publish to MQTT Broker
    while True:
        ### Set the MQTT Message Payload
        JSONpayload = logi.get_payload()

        ### Publish the Message to MQTT
        input("Press enter to publish")
        logi.publish_mqtt(JSONpayload, myAWSIoTMQTTClient)
        logging.info("Wait 15 seconds...")
        time.sleep(15)