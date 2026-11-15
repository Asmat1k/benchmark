package echo

import "sync/atomic"

type phaseCounts struct {
	received, invalid, attempted, echoed, failures atomic.Uint64
}

var counts [2]phaseCounts
var Active atomic.Int64

func Receive(p []byte, ready bool) *phaseCounts {
	if !ready || len(p) < 6 || p[5] > 1 {
		return nil
	}
	c := &counts[p[5]]
	c.received.Add(1)
	return c
}

func (c *phaseCounts) Valid(valid bool) {
	if c == nil {
		return
	}
	if valid {
		c.attempted.Add(1)
	} else {
		c.invalid.Add(1)
	}
}

func (c *phaseCounts) Written(ok bool) {
	if c == nil {
		return
	}
	if ok {
		c.echoed.Add(1)
	} else {
		c.failures.Add(1)
	}
}

func Snapshot() map[string]any {
	out := map[string]any{"active": Active.Load()}
	for i, name := range []string{"warmup", "measurement"} {
		c := &counts[i]
		out[name] = map[string]uint64{"received": c.received.Load(), "invalid": c.invalid.Load(), "write_attempted": c.attempted.Load(), "echoed": c.echoed.Load(), "errors": c.failures.Load()}
	}
	return out
}
