package protocol

import "encoding/binary"

const Size = 256

func Valid(p []byte) bool {
	if len(p) != Size || binary.BigEndian.Uint32(p) != 0x42575431 || p[4] != 1 || p[5] > 1 || binary.BigEndian.Uint16(p[6:]) != 0 {
		return false
	}
	seq := binary.BigEndian.Uint64(p[16:])
	for i := 24; i < len(p); i++ {
		if p[i] != byte(seq+uint64(i)) {
			return false
		}
	}
	return true
}
