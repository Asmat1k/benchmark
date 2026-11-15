import sys
import calibration_probe as probe
probe.COUNT = 5000
probe.MAX_ECHO_WAIT_NS = 0 if sys.argv[3].startswith('poll0') else probe.MAX_ECHO_WAIT_NS
probe.send(sys.argv[1], False, sys.argv[2])
