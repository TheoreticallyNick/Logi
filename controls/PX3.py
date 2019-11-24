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

    def getPres(self):
        bits = ADC.read_raw(self.ADCpin)
        p = (bits * 124 / 1455) - 114.70

        return p

def main():
    
    ADC.setup()
    
    p = Pressure("P9_39")
    print("Raw Bits: %.2f"%(p.getRaw()))
    print("Analog Voltage: %.2f"%(p.getVoltage()))
    print("Pressure: %.2f"%(p.getPres()))
            
if __name__=="__main__":
    main()
