import sys
import calibration_probe as probe
probe.send(sys.argv[1], False, sys.argv[2])
