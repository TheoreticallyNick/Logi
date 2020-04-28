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

    def get_raw(self):
        raw = ADC.read_raw(self.ADCpin)
        
        return raw

    def get_voltage(self):
        volts = ADC.read(self.ADCpin)

        return volts

    def get_lvl(self):
        try:
            volts = ADC.read(self.ADCpin)
            lev = (volts * 95.08) + 4.467
            lev = round(lev, 2)
        except:
            lev = 999
            pass

        return lev

def main():
    
    ADC.setup()
    
    l = FluidLevel("P9_39")
    print("Raw Bits: %.4f"%(l.get_raw()))
    print("Analog Voltage: %.4f"%(l.get_voltage()))
    print("Fluid Level: %.2f"%(l.get_lvl()))
            
if __name__=="__main__":
    main()
