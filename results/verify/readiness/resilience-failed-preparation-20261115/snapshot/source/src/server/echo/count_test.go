package echo

import (
	"testing"
)

func TestPhaseCounters(t *testing.T) {
	before := Snapshot()
	if Receive([]byte("READY"), false) != nil || Receive([]byte{0}, true) != nil {
		t.Fatal("handshake or short frame counted")
	}
	var absent *phaseCounts
	absent.Valid(true)
	absent.Written(true)
	for phase, name := range []string{"warmup", "measurement"} {
		frame := make([]byte, 256)
		frame[5] = byte(phase)
		counts := Receive(frame, true)
		counts.Valid(true)
		counts.Written(true)
		counts = Receive(frame, true)
		counts.Valid(true)
		counts.Written(false)
		counts = Receive(frame, true)
		counts.Valid(false)
		after := Snapshot()[name].(map[string]uint64)
		prior := before[name].(map[string]uint64)
		for field, delta := range map[string]uint64{"received": 3, "invalid": 1, "write_attempted": 2, "echoed": 1, "errors": 1} {
			if after[field]-prior[field] != delta {
				t.Fatalf("%s/%s: got %d", name, field, after[field]-prior[field])
			}
		}
	}
}
