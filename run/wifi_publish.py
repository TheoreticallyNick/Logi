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

    ### Set the MQTT Message Payload
    JSONpayload = logi.get_payload()

    ### Publish to MQTT Broker
    att = 1
    while True:
        if att == 4:
            logging.error('Three MQTT publish attempts failed, publish cycle skipped')
            break
        try:
            logi.publish_mqtt(JSONpayload, myAWSIoTMQTTClient)
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