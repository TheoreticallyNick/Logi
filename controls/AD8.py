import Adafruit_BBIO.ADC as ADC
import time

'''
Pinout Reference Table:
    "AIN4", "P9_33"
    "AIN6", "P9_35"
    "AIN5", "P9_36"
    "AIN2", "P9_37"
    "AIN3", "P9_38"
    "AIN0", "P9_39"
    "AIN1", "P9_40"
'''

class Thermocouple:
    def __init__(self, ADCpin):
        self.ADCpin = ADCpin

    def getRaw(self):
        raw = ADC.read_raw(self.ADCpin)
        
        return raw

    def getVoltage(self):
        volts = ADC.read(self.ADCpin)

        return volts

    def getTemp(self):
        volts = ADC.read(self.ADCpin)
        t = (volts-.55)/.005

        return t

def main():
    
    ADC.setup()
    
    tc = Thermocouple("P9_40")
    print("Raw Bits: %.2f"%(tc.getRaw()))
    print("Analog Voltage: %.2f"%(tc.getVoltage()))
    print("Temperature: %.2f"%(tc.getTemp()))
            
if __name__=="__main__":
    main()