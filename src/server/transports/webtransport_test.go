package transports

import (
	"bench/protocol"
	"bytes"
	"encoding/binary"
	"errors"
	"io"
	"testing"
)

type shortWriter struct{ input, output bytes.Buffer }

// Read reads bytes from the test input.
func (s *shortWriter) Read(p []byte) (int, error) { return s.input.Read(p) }

// Write writes one byte to simulate a short write.
func (s *shortWriter) Write(p []byte) (int, error) { return s.output.Write(p[:1]) }

// TestStream checks stream echo handling of short writes.
func TestStream(t *testing.T) {
	frame := make([]byte, protocol.Size)
	binary.BigEndian.PutUint32(frame, 0x42575431)
	frame[4] = 1
	for i := 24; i < len(frame); i++ {
		frame[i] = byte(i)
	}
	for _, tc := range []struct {
		name     string
		payload  []byte
		expected error
	}{
		{"complete", frame, io.EOF},
		{"truncated", frame[:255], io.ErrUnexpectedEOF},
	} {
		// Check the stream reply and expected termination error.
		t.Run(tc.name, func(t *testing.T) {
			stream := new(shortWriter)
			stream.input.WriteString("READY")
			stream.input.Write(tc.payload)
			if err := StreamEcho(stream); !errors.Is(err, tc.expected) {
				t.Fatalf("got %v", err)
			}
			expected := []byte("ACK")
			if tc.expected == io.EOF {
				expected = append(expected, frame...)
			}
			if !bytes.Equal(stream.output.Bytes(), expected) {
				t.Fatal("incorrect echo")
			}
		})
	}
}
