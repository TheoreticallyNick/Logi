import Adafruit_BBIO.GPIO as GPIO
import time
import threading

class CommandLED:

    def __init__(self, GPIOpin):
        self.GPIOpin = GPIOpin
        GPIO.setup(self.GPIOpin, GPIO.OUT)
        
    def lightOn(self):
        GPIO.output(self.GPIOpin, 1)
    
    def lightFlash(self):
        GPIO.output(self.GPIOpin, 1)
        time.sleep(.5)
        GPIO.output(self.GPIOpin, 0)
        time.sleep(.5)
        
    def lightHeart(self):
        GPIO.output(self.GPIOpin, 1)
        time.sleep(.75)
        GPIO.output(self.GPIOpin, 0)
        time.sleep(.05)
        GPIO.output(self.GPIOpin, 1)
        time.sleep(.2)
        GPIO.output(self.GPIOpin, 0)
        time.sleep(.05)     
        
    def lightOff(self):
        GPIO.output(self.GPIOpin, 0) 

def lightLoop(lightObj):
    t = threading.currentThread()
    while getattr(t, "do_run", True):
        lightObj.lightHeart()

def main():
    
    ledr = CommandLED("P8_7")

    t = threading.Thread(name='lightLoop', target=lightLoop, args=(ledr,))
    t.start()
    
    time.sleep(10)
    t.do_run = False
    t.join()

    GPIO.cleanup()
    
if __name__=="__main__":
    main()