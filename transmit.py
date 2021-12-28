import sys
import time
import RPi.GPIO as GPIO

if len(sys.argv) < 2:
    print("Usage: python transmit.py [action]")
    sys.exit()

action = sys.argv[1]
with open(f"{action}-sequence.txt", "r") as f:
    code = f.read()

with open("timing.txt", "r") as f:
    shortTime = float(f.readline())
    longTime = float(f.readline())
    delayTime = float(f.readline())

# Transmit the sequence 10 times, in case of 
# failed transmissions. 
numTransmissions = 10

transmitPin = 2
GPIO.setmode(GPIO.BCM)
GPIO.setup(transmitPin, GPIO.OUT)

for _ in range(numTransmissions):
    for bit in code:
        if bit == '1':
            # 1 indicates a short on followed
            # by a long off. 
            GPIO.output(transmitPin, 1)
            time.sleep(shortTime)
            GPIO.output(transmitPin, 0)
            time.sleep(longTime)
        elif bit == '0':
            # 0 indicates a long on followed
            # by a short off. 
            GPIO.output(transmitPin, 1)
            time.sleep(longTime)
            GPIO.output(transmitPin, 0)
            time.sleep(shortTime)
        else:
            continue
    
    # Add a delay between consecutive transmissions. 
    GPIO.output(transmitPin, 0)
    time.sleep(delayTime)

GPIO.cleanup()