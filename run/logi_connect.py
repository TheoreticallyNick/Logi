

class LogiConnect:

    def __init__(self, mqtt):
        self.mqtt = mqtt

    def buildCloudObject():
        ### Redundancy for Connecting to the Onboard Modem ###
        logging.info('Connecting to on-board modem and building new cloud object...')
        attempts = 1
        err = ""

        while attempts <= 4:
            cloud = None
            logging.info('- Modem Connection Attempt %i -', attempts)

            if attempts == 4:
                logging.critical('FATAL ERROR: %s', err)
                logging.critical('3 attempts made to connect to MQTT Client')
                os._exit(1)  

            try:
                cloud = CustomCloud(None, network='cellular')
                break
            
            except NetworkError:
                logging.error('ERR101: Could not find modem')
                err = err + "E101; "
                rtcWake("5", "standby")
                time.sleep(15)
                attempts += 1
                continue
            
            except SerialError:
                logging.error('ERR103: Could not find usable serial port')
                err = err + "E103; "
                rtcWake("5", "standby")
                time.sleep(15)
                attempts += 1
                continue

        logging.info('--> Successfully found USB Modem')           
        return cloud, err

    def connectToCellular(cloud):
        ### Redundancy for Connecting to the Cellular Network ###
        logging.info('Connecting to Cellular Network...')    
        attempts = 1
        err = ""
        
        while attempts <= 4:
            logging.info('- Cellular Network Connection Attempt %i -', attempts)

            if attempts == 4:
                logging.critical('FATAL ERROR: %s', err)
                logging.critical('3 attempts made to connect to MQTT Client')
                os._exit(1)  
            
            try: 
                result = cloud.network.connect()

            except PPPError:
                logging.error('ERR105: Could not start a PPP Session -- Other Sessions still open')
                err = err + "E105; "
                
                if attempts < 2:
                    cleanKill(cloud)
                    cloud , errx = buildCloudObject()
                    err = err + errx
                    antennaCycle(cloud)
                    attempts += 1
                    continue
                
                else:
                    cleanKill(cloud)
                    rtcWake("5", "standby")
                    time.sleep(15)
                    cloud , errx = buildCloudObject()
                    err = err + errx
                    antennaCycle(cloud)
                    attempts += 1
                    continue


            except SerialException:
                logging.error('ERR121: Modem reports readiness but returns no data')
                err = err + "E121; "
                
                if attempts < 2:
                    cleanKill(cloud)
                    cloud , errx = buildCloudObject()
                    err = err + errx
                    antennaCycle(cloud)
                    attempts += 1
                    continue
                
                else:
                    cleanKill(cloud)
                    rtcWake("5", "standby")
                    time.sleep(15)
                    cloud , errx = buildCloudObject()
                    err = err + errx
                    antennaCycle(cloud)
                    attempts += 1
                    continue

            if result == True:
                break

            else:
                logging.error('ERR107: Could not connect to cellular network')
                err = err + "E107; "
                
                if attempts < 2:
                    cleanKill(cloud)
                    cloud , errx = buildCloudObject()
                    err = err + errx
                    antennaCycle(cloud)
                    attempts += 1
                    continue
                
                else:
                    cleanKill(cloud)
                    rtcWake("5", "standby")
                    time.sleep(15)
                    cloud , errx = buildCloudObject()
                    err = err + errx
                    antennaCycle(cloud)
                    attempts += 1
                    continue

        logging.info('--> Successfully Connected to Cell Network')
        return cloud, err

    def connectMQTT(client, cloud):
        ### Redundancy for Connecting to MQTT Client ###
        logging.info('Connecting to MQTT...')
        attempts = 1
        err = ""

        while attempts <= 4:
            logging.info('- MQTT Client Connection Attempt %i -', attempts)

            if attempts == 4:
                logging.critical('FATAL ERROR: %s', err)
                logging.critical('3 attempts made to connect to MQTT Client')
                os._exit(1) 

            try:
                result = client.connect()

            except gaierror:
                logging.error('ERR109: Temporary failure in DNS server name resolution')
                err = err + "E109; "
                cleanKill(cloud)
                rtcWake("5", "standby")
                time.sleep(15)
                cloud , errx = buildCloudObject()
                err = err + errx
                antennaCycle(cloud)
                cloud, errx = connectToCellular(cloud)
                err = err + errx
                attempts += 1
                continue

            except connectTimeoutException:
                logging.error('ERR121: MQTT client connection timeout')
                err = err + "E121; "
                cleanKill(cloud)
                rtcWake("5", "standby")
                time.sleep(15)
                cloud , errx = buildCloudObject()
                err = err + errx
                antennaCycle(cloud)
                cloud, errx = connectToCellular(cloud)
                err = err + errx
                attempts += 1
                continue
                
            if result == True:
                time.sleep(5)
                break
            else:
                logging.error('ERR111: Could not Connect to MQTT Client')
                err = err + "E111; "
                cleanKill(cloud)
                rtcWake("5", "standby")
                time.sleep(15)
                cloud , errx = buildCloudObject()
                err = err + errx
                antennaCycle(cloud)
                cloud, errx = connectToCellular(cloud)
                err = err + errx
                attempts += 1
                continue

        logging.info('--> Successfully Connected to MQTT Client')
        return cloud, err

    def cleanKill(cloud):
        ### Turns off and destroys all PPP sessions to the cellular network
        logging.info('Disconnecting All Sessions...')
        cloud.network.disconnect()

        for proc in psutil.process_iter():

            try:
                pinfo = proc.as_dict(attrs=['pid', 'name'])
            except:
                raise HologramError('Failed to check for existing PPP sessions')
            if 'pppd' in pinfo['name']:
                print('Found existing PPP session on pid: %s' % pinfo['pid'])
                print('Killing pid %s now' % pinfo['pid'])
                psutil.Process(pinfo['pid']).kill()
                print(kill_proc_tree(pinfo['pid']))
        
        time.sleep(5)

    def kill_proc_tree(pid, sig=signal.SIGTERM, include_parent=True, timeout=None, on_terminate=None):
        """Kill a process tree (including grandchildren) with signal
        "sig" and return a (gone, still_alive) tuple.
        "on_terminate", if specified, is a callabck function which is
        called as soon as a child terminates.
        """
        assert pid != os.getpid(), "won't kill myself"
        parent = psutil.Process(pid)
        children = parent.children(recursive=True)
        
        if include_parent:
            children.append(parent)
        
        for p in children:
            p.send_signal(sig)
        
        gone, alive = psutil.wait_procs(children, timeout=timeout, callback=on_terminate)
        
        return (gone, alive)

    def antennaCycle(cloud):
        
        logging.info('Cycling the radio antenna...')
        cloud.network.modem.radio_power(False)
        time.sleep(15)
        cloud.network.modem.radio_power(True)
        time.sleep(15)

    def lvlOne():

        seq = [cleanKill(), antennaCycle(), buildCloudObject(), connectToCellular(), connectMQTT]
        
        return

    def lvlTwo():

        seq = [cleanKill(), antennaCycle(), buildCloudObject(), connectToCellular(), connectMQTT]
        
        return