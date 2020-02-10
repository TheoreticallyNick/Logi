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

class FluidLevel:
    def __init__(self, ADCpin):
        self.ADCpin = ADCpin

    def getRaw(self):
        raw = ADC.read_raw(self.ADCpin)
        
        return raw

    def getVoltage(self):
        volts = ADC.read(self.ADCpin)

        return volts

    def getLev(self):
        volts = ADC.read(self.ADCpin)
        lev = (volts * 92.105) + 3.422

        return lev

def main():
    
    ADC.setup()
    
    l = FluidLevel("P9_39")
    print("Raw Bits: %.2f"%(l.getRaw()))
    print("Analog Voltage: %.2f"%(l.getVoltage()))
    print("Fluid Level: %.2f"%(l.getLev()))
            
if __name__=="__main__":
    main()
