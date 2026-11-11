package main

import (
	"bench/echo"
	"bench/transports"
	"crypto/tls"
	"encoding/json"
	"flag"
	"github.com/quic-go/quic-go"
	"github.com/quic-go/quic-go/http3"
	wt "github.com/quic-go/webtransport-go"
	"log"
	"net"
	"net/http"
	"os"
	"os/signal"
	"path/filepath"
	"syscall"
	"time"
)

type noDelayListener struct{ *net.TCPListener }

func (l noDelayListener) Accept() (net.Conn, error) {
	c, err := l.AcceptTCP()
	if err != nil {
		return nil, err
	}
	if err = c.SetNoDelay(true); err != nil {
		c.Close()
		return nil, err
	}
	return c, nil
}

func main() {
	addr := flag.String("addr", ":8443", "listen address")
	certs := flag.String("certs", "/certs/good", "leaf directory")
	flag.Parse()
	snapshots := make(chan os.Signal, 1)
	signal.Notify(snapshots, syscall.SIGUSR1)
	go func() {
		for range snapshots {
			data, err := json.Marshal(echo.Snapshot())
			if err == nil {
				err = os.WriteFile("/tmp/counters.partial", data, 0644)
			}
			if err == nil {
				err = os.Rename("/tmp/counters.partial", "/tmp/counters.json")
			}
			if err != nil {
				log.Print(err)
			}
		}
	}()
	cert, err := tls.LoadX509KeyPair(filepath.Join(*certs, "cert.pem"), filepath.Join(*certs, "key.pem"))
	if err != nil {
		log.Fatal(err)
	}
	cfg := &tls.Config{Certificates: []tls.Certificate{cert}, MinVersion: tls.VersionTLS13, SessionTicketsDisabled: true, NextProtos: []string{"http/1.1"}}
	h3 := cfg.Clone()
	h3.NextProtos = []string{"h3"}
	qm := http.NewServeMux()
	quicConfig := &quic.Config{
		Versions:                       []quic.Version{quic.Version1},
		EnableDatagrams:                true,
		HandshakeIdleTimeout:           5 * time.Second,
		MaxIdleTimeout:                 30 * time.Second,
		InitialPacketSize:              1200,
		DisablePathMTUDiscovery:        true,
		InitialStreamReceiveWindow:     1 << 20,
		MaxStreamReceiveWindow:         1 << 20,
		InitialConnectionReceiveWindow: 4 << 20,
		MaxConnectionReceiveWindow:     4 << 20,
		MaxIncomingStreams:             16,
		MaxIncomingUniStreams:          16,
	}
	server := wt.Server{
		H3:          http3.Server{Addr: *addr, TLSConfig: h3, Handler: qm, QUICConfig: quicConfig},
		CheckOrigin: func(r *http.Request) bool { return r.Header.Get("Origin") == transports.Origin },
	}
	qm.HandleFunc("/wt", transports.WebTransport(&server))
	go func() { log.Fatal(server.ListenAndServe()) }()
	mux := http.NewServeMux()
	mux.HandleFunc("/ws", transports.WebSocket)
	mux.Handle("/", http.FileServer(http.Dir("/page")))
	ln, err := net.Listen("tcp", *addr)
	if err != nil {
		log.Fatal(err)
	}
	tcp := http.Server{Handler: mux, TLSConfig: cfg, TLSNextProto: map[string]func(*http.Server, *tls.Conn, http.Handler){}}
	log.Fatal(tcp.ServeTLS(noDelayListener{ln.(*net.TCPListener)}, "", ""))
}
