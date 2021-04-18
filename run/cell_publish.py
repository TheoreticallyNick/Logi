#!/bin/bash
from logi_connect import LogiConnect
import logging

### Create LogiConnect Object
logi = LogiConnect()

<<<<<<< HEAD
logging.info('###---------- Logi Cellular v1.6 Program Start ----------###')
=======
logging.info('###---------- Logi Cellular v1.7 Program Start ----------###')
>>>>>>> updates

myAWSIoTMQTTClient, callBackContainer = logi.init_mqtt(logi.mqtt)

### Schema Version
logging.info('MQTT Schema: %s', logi.schema) 

### Connection Cycle
logging.info('Initial connection and calibration...')

while True:

    try:
        logi.create_cloud()
        logi.antenna_cycle()
        logi.cell_connect()
        break

    except:
        logi.rtc_wake('10', 'mem')
        
        try:
            logi.clean_kill()
        except:
            pass

        continue

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

        if att == 4:
            logi.skip_cycle()
            att = 1
            continue
        
        if logi.cycle_cnt != 1: 
            try:
                logi.create_cloud()
                logi.antenna_cycle()
                logi.cell_connect()
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
        
        else:
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

    ### Set the MQTT Message Payload
    JSONpayload = logi.get_payload()

    ### Publish to MQTT Broker
    att = 1
    while True:
        if att == 4:
            logging.error('Three MQTT publish attempts failed, publish cycle skipped')
            break
        try:
<<<<<<< HEAD
            logi.publish_mqtt(JSONpayload, myAWSIoTMQTTClient)
=======
            if logi.cycle_cnt == 1:
                logi.publish_mqtt(JSONpayload, myAWSIoTMQTTClient, test = True)
            else:
                logi.publish_mqtt(JSONpayload, myAWSIoTMQTTClient, test = False)
>>>>>>> updates
        except:
            logging.error('ERR141: Unable to Publish to MQTT, publish cycle skipped')
            logi.err = logi.err + 'ERR141; '
            att += 1
            continue
        finally:
            logi.err = ''
            break

    logi.cycle_cnt = logi.cycle_cnt + 1
    
    ### Kill all open PPP connections and processes
    logging.info('Killing all PPP connections...')
    try:
        logi.clean_kill()
    except:
        pass

    ### Bash Command to Enter Sleep Cycle
    logging.info('Wake up time: %s', logi.wake_time)
    sleep_time = logi.sleep_calc(logi.wake_time)
    logging.info('Sleep time in sec: %s', str(sleep_time))
    logi.rtc_wake(str(sleep_time), 'mem')