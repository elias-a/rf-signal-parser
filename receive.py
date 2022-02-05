import sys
import pickle
import numpy as np
from os.path import exists
from datetime import datetime
from itertools import groupby 

try:
    import matplotlib.pyplot as plt
except:
    import matplotlib
    matplotlib.use("GTK3Agg")
    import matplotlib.pyplot as plt

duration_sec = 3

def receiveData(action):
    import RPi.GPIO as GPIO

    receivePin = 2
    GPIO.setmode(GPIO.BCM)
    GPIO.setup(receivePin, GPIO.IN)

    # Record the received signal. 
    print("Receiving signal...")
    timeElapsed_sec = 0
    startTime = datetime.now()
    receivedInput = []
    while timeElapsed_sec < duration_sec:
        timeStep = datetime.now() - startTime
        receivedInput.append((timeStep.seconds + timeStep.microseconds / 10**6, GPIO.input(receivePin)))
        timeElapsed_sec = timeStep.seconds

    print("Done receiving signal...")
    GPIO.cleanup()

    with open(f"{action}.txt", "wb") as f:
        pickle.dump(receivedInput, f)

if len(sys.argv) < 2:
    print("Usage: python receive.py action")
    sys.exit()

# Receive signal or read signal data from file. 
action = sys.argv[1]
filePath = f"{action}.txt"
fileExists = exists(filePath)
if not fileExists:
    receiveData(action)

with open(filePath, "rb") as f:
    receivedInput = pickle.load(f)

# Determine the durations of consecutive on/off signals. 
durations = []
durationsAndBits = []
for key, group in groupby(receivedInput, lambda el: el[1]):
    startTime, bit = next(group)
    *_, last = group
    endTime = last[0]
    durations.append(endTime - startTime)
    durationsAndBits.append((endTime - startTime, bit, startTime, endTime))

# Split a list into two lists depending on a threshold. 
def splitByThreshold(data):
    q1, q3 = np.percentile(data, [25, 75])
    iqr = q3 - q1
    threshold = q3 + 1.5 * iqr

    lower = [el for el in data if el < threshold]
    upper = [el for el in data if el >= threshold]
    return (lower, upper)

# Split into 2 datasets, based on Q3 + 1.5 * IQR. Use the 
# lower duration dataset to determine the transmission sequence, 
# and use the higher duration dataset to get the delay between 
# consecutive transmissions. 
sequenceDurations, upperDataset = splitByThreshold(durations)

# Split the higher duration dataset again, to filter out the 
# highest duration values, which are likely not part of the
# signal. 
delayDurations, _ = splitByThreshold(upperDataset)

# Select the bins with the highest and second highest
# counts from the shorter duration dataset. The short 
# and long duration signals will fall in these bins. 
numBinsShort = 3
sequenceDurationCounts, sequenceDurationBins = np.histogram(sequenceDurations, bins=numBinsShort)

sequenceDurationIndex = np.argmax(sequenceDurationCounts)
sequenceBin1 = (sequenceDurationBins[sequenceDurationIndex], sequenceDurationBins[sequenceDurationIndex + 1])

# Remove the largest count from the list in order to find
# the second largest count. 
sequenceCountsFiltered = np.concatenate((sequenceDurationCounts[0:sequenceDurationIndex], sequenceDurationCounts[sequenceDurationIndex + 1:]))
sequenceBinsFiltered = np.concatenate((sequenceDurationBins[0:sequenceDurationIndex], sequenceDurationBins[sequenceDurationIndex + 1:]))
sequenceFilteredIndex = np.argmax(sequenceCountsFiltered)
sequenceBin2 = (sequenceBinsFiltered[sequenceFilteredIndex], sequenceBinsFiltered[sequenceFilteredIndex + 1])

# Determine which bin contains the short signal and 
# which bin contains the long signal. 
sequenceBins = (sequenceBin1, sequenceBin2)
shortestIndex = np.argmin([sequenceBin1[0], sequenceBin2[0]])
shortBin = sequenceBins[shortestIndex]
longBin = sequenceBins[(shortestIndex + 1) % 2]

# Select the bin with the highest count from the longer duration 
# dataset. The delay between consecutive transmissions will fall 
# in this bin. 
delayDurationCounts, delayDurationBins = np.histogram(delayDurations)
delayDurationIndex = np.argmax(delayDurationCounts)
delayBin = (delayDurationBins[delayDurationIndex], delayDurationBins[delayDurationIndex + 1])

# Each transmission is followed by a long delay. Look for two such
# delays, and then search for the transmission sequence in between. 
delays = []
waveform = []
shortTimes = []
longTimes = []
delayTimes = []
for duration, bit, start, end in durationsAndBits:
    if duration >= delayBin[0] and duration <= delayBin[1]:
        delays.append((start, end))
        delayTimes.append(duration)

        if len(delays) == 2:
            # Since the sequence is followed by a long 0,
            # the sequence must end with a 1, encoded as 
            # s followed by l. But the l will have been grouped
            # with the following long 0 delay, so append the 
            # l here at the end of the sequence. 
            waveform.append('l')

            # We're interested in parsing a single sequence, 
            # so exit the loop after finding the second delay. 
            break

        continue

    # The sequence is transmitted between delays. Note that 
    # the sequence must begin with a 1, since the sequence 
    # is preceded by a long 0. With this in mind, we'll 
    # (arbitrarily) relabel a short 1 followed by a long 0 
    # as "1", and a long 1 followed by a short 0 as a "0". 
    # As long as the transmitting program understands this
    # convention, it does not matter what arbitrary methodology
    # is chosen. 
    if len(delays) == 1:
        if duration >= shortBin[0] and duration <= shortBin[1]:
            waveform.append('s')
            shortTimes.append(duration)
        elif duration >= longBin[0] and duration <= longBin[1]:
            waveform.append('l')
            longTimes.append(duration)
        else:
            print('ERROR!')

# Transform the pattern of short and long values to a sequence
# of 1s and 0s, using the methodology described above. 
index = 0
sequence = ''
while index < len(waveform):
    signal = waveform[index] + waveform[index + 1]
    if signal == 'sl':
        sequence += '1'
    elif signal == 'ls':
        sequence += '0'

    index += 2

# Save code to a file. 
with open(f"{action}-sequence.txt", "w") as f:
    f.write(sequence)

# The timing of each on/off transmission will be slightly
# different, so choose the median time. 
shortTime = np.median(shortTimes)
longTime = np.median(longTimes)
delayTime = np.median(delayTimes)

# Save timing data to a file. 
with open("timing.txt", "w") as f:
    f.writelines([str(shortTime), "\n", str(longTime), "\n", str(delayTime)])

fig, ax = plt.subplots(3, 3)

ax[0, 0].boxplot(durations)
ax[0, 1].boxplot(sequenceDurations)
ax[0, 2].boxplot(delayDurations)

ax[1, 0].hist(sequenceDurations, bins=numBinsShort)
ax[1, 1].hist(upperDataset)
ax[1, 2].hist(delayDurations)

ax[2, 0].plot(*zip(*receivedInput))
ax[2, 0].axis([0, duration_sec, -0.5, 1.5])

ax[2, 1].plot(*zip(*receivedInput))
ax[2, 1].axis([delays[0][0], delays[1][1], -0.1, 1.1])

plt.show()