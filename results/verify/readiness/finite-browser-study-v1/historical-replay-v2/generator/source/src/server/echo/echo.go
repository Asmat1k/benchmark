package echo

import (
	"bench/protocol"
	"errors"
)

func Reply(p []byte, ready bool) ([]byte, error) {
	if !ready {
		if string(p) != "READY" {
			return nil, errors.New("expected READY")
		}
		return []byte("ACK"), nil
	}
	if !protocol.Valid(p) {
		return nil, errors.New("invalid fixed256 frame")
	}
	return p, nil
}
