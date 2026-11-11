package transports

import (
	"bench/echo"
	"bench/protocol"
	"github.com/quic-go/quic-go/http3"
	wt "github.com/quic-go/webtransport-go"
	"io"
	"log"
	"net/http"
)

func StreamEcho(s io.ReadWriter) error {
	size := len("READY")
	for ready := false; ; ready = true {
		p := make([]byte, size)
		if _, err := io.ReadFull(s, p); err != nil {
			return err
		}
		counts := echo.Receive(p, ready)
		reply, err := echo.Reply(p, ready)
		counts.Valid(err == nil)
		if err != nil {
			return err
		}
		for len(reply) > 0 {
			n, err := s.Write(reply)
			if err != nil {
				counts.Written(false)
				return err
			}
			if n == 0 {
				counts.Written(false)
				return io.ErrShortWrite
			}
			reply = reply[n:]
		}
		counts.Written(true)
		size = protocol.Size
	}
}

func WebTransport(server *wt.Server) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		session, err := server.Upgrade(w, r)
		if err != nil {
			log.Printf("WT upgrade: %v", err)
			return
		}
		echo.Active.Add(1)
		defer echo.Active.Add(-1)
		defer session.CloseWithError(0, "finished")
		state := session.ConnectionState()
		log.Printf("peer HTTP/3 SETTINGS=%+v server additional SETTINGS=%v", w.(http3.Hijacker).Connection().Settings(), server.H3.AdditionalSettings)
		log.Printf("WT request=%s http=%s alpn=%s quic=%s datagrams=%t draft-response=%s", r.Method, r.Proto, state.TLS.NegotiatedProtocol, state.Version, state.SupportsDatagrams, w.Header().Get("Sec-Webtransport-Http3-Draft"))
		if r.URL.Query().Get("mode") == "datagram" {
			for ready := false; ; ready = true {
				p, err := session.ReceiveDatagram(session.Context())
				if err != nil {
					return
				}
				counts := echo.Receive(p, ready)
				reply, err := echo.Reply(p, ready)
				counts.Valid(err == nil)
				if err != nil {
					return
				}
				err = session.SendDatagram(reply)
				counts.Written(err == nil)
				if err != nil {
					return
				}
			}
		}
		s, err := session.AcceptStream(session.Context())
		if err != nil {
			return
		}
		go func() {
			if _, err := session.AcceptStream(session.Context()); err == nil {
				session.CloseWithError(1, "extra stream")
			}
		}()
		if err := StreamEcho(s); err != nil && err != io.EOF {
			log.Printf("WT stream: %v", err)
		}
	}
}
