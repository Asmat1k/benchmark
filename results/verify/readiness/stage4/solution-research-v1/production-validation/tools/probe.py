import contextlib
import io
import json
import os
import sys
import calibration_probe as probe
output=io.StringIO()
with contextlib.redirect_stdout(output):
    probe.send(sys.argv[1],False,sys.argv[2])
result=json.loads(output.getvalue())
result['sender_cpu_after']=sorted(os.sched_getaffinity(0))
print(json.dumps(result))
