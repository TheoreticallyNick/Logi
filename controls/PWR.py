import Adafruit_BBIO.GPIO as GPIO
import time

class Battery:
    def __init__(self, GPIOpin):
        self.GPIOpin = GPIOpin
        GPIO.setup(self.GPIOpin, GPIO.IN)

    def getStatus(self):

        print(GPIO.input(self.GPIOpin))

        if GPIO.input(self.GPIOpin):
            return True
        else:
            return False

def main():

    b = Battery("P8_9")

    if b.getStatus():
        print("Battery Okay")
    else:
        print("Battery Low")
    
    
            
if __name__=="__main__":
    main()
