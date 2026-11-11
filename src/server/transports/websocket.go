package transports

import (
	"bench/echo"
	"bench/protocol"
	"context"
	"github.com/coder/websocket"
	"log"
	"net/http"
)

const Origin = "https://bench.test:8443"

func WebSocket(w http.ResponseWriter, r *http.Request) {
	if r.Header.Get("Origin") != Origin {
		http.Error(w, "origin", http.StatusForbidden)
		return
	}
	conn, err := websocket.Accept(w, r, &websocket.AcceptOptions{OriginPatterns: []string{"https://bench.test:8443"}, CompressionMode: websocket.CompressionDisabled})
	if err != nil {
		return
	}
	defer conn.CloseNow()
	conn.SetReadLimit(protocol.Size)
	log.Printf("WSS upgrade=101 http=%s alpn=%s tls=%x resumed=%t", r.Proto, r.TLS.NegotiatedProtocol, r.TLS.Version, r.TLS.DidResume)
	for ready := false; ; ready = true {
		kind, p, err := conn.Read(r.Context())
		if err != nil {
			return
		}
		reply, err := echo.Reply(p, ready)
		if kind != websocket.MessageBinary || err != nil {
			conn.Close(websocket.StatusProtocolError, "invalid message")
			return
		}
		if conn.Write(context.Background(), websocket.MessageBinary, reply) != nil {
			return
		}
	}
}
