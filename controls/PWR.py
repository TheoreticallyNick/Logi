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

class Battery:
    def __init__(self, ADCpin):
        self.ADCpin = ADCpin

    def getRaw(self):
        raw = ADC.read_raw(self.ADCpin)
        
        return raw

    def get_voltage(self):
        volts = ADC.read(self.ADCpin)

        volts = round(volts, 2)

        return volts

def main():
    bat = Battery('P9_37')

    ADC.setup()

    print("Raw Bits: %.2f"%(bat.getRaw()))
    print("Analog Voltage: %.2f"%(bat.getVoltage()))    
    
            
if __name__=="__main__":
    main()
