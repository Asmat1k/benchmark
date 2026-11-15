import sys
import calibration_probe as probe
probe.COUNT=5000
probe.send(sys.argv[1], False, sys.argv[2])
