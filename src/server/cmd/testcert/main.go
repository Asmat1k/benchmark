package main

import (
	"crypto/ecdsa"
	"crypto/elliptic"
	"crypto/rand"
	"crypto/sha256"
	"crypto/x509"
	"crypto/x509/pkix"
	"encoding/hex"
	"encoding/json"
	"encoding/pem"
	"log"
	"math/big"
	"os"
	"path/filepath"
	"time"
)

// check stops certificate generation when an error occurs.
func check(err error) {
	if err != nil {
		log.Fatal(err)
	}
}

// key generates an ECDSA private key.
func key() *ecdsa.PrivateKey {
	k, err := ecdsa.GenerateKey(elliptic.P256(), rand.Reader)
	check(err)
	return k
}

// write writes PEM data with the supplied file mode.
func write(path, kind string, data []byte, mode os.FileMode) {
	check(os.WriteFile(path, pem.EncodeToMemory(&pem.Block{Type: kind, Bytes: data}), mode))
}

// main runs the program entry point.
func main() {
	root := os.Args[1]
	public := filepath.Join(root, "public")
	check(os.MkdirAll(public, 0755))
	now := time.Now().UTC()
	caKey := key()
	ca := &x509.Certificate{SerialNumber: big.NewInt(1), Subject: pkix.Name{CommonName: "Local bench CA"}, NotBefore: now.AddDate(0, 0, -30), NotAfter: now.AddDate(0, 0, 30), IsCA: true, BasicConstraintsValid: true, KeyUsage: x509.KeyUsageCertSign}
	caDER, err := x509.CreateCertificate(rand.Reader, ca, ca, &caKey.PublicKey, caKey)
	check(err)
	write(filepath.Join(public, "ca.crt"), "CERTIFICATE", caDER, 0644)
	pins := map[string]string{}
	for index, name := range []string{"good", "wrong-san", "expired", "unknown-ca"} {
		start := now.Add(-time.Minute)
		host := "bench.test"
		issuer := caKey
		authority := ca
		if name == "expired" {
			start = now.AddDate(0, 0, -14)
		}
		if name == "wrong-san" {
			host = "wrong.test"
		}
		if name == "unknown-ca" {
			issuer = key()
			unknown := *ca
			unknown.Subject = pkix.Name{CommonName: "Untrusted test CA"}
			authority = &unknown
		}
		leafKey := key()
		leaf := &x509.Certificate{SerialNumber: big.NewInt(int64(index + 2)), Subject: pkix.Name{CommonName: host}, DNSNames: []string{host}, NotBefore: start, NotAfter: start.AddDate(0, 0, 13), KeyUsage: x509.KeyUsageDigitalSignature, ExtKeyUsage: []x509.ExtKeyUsage{x509.ExtKeyUsageServerAuth}}
		der, err := x509.CreateCertificate(rand.Reader, leaf, authority, &leafKey.PublicKey, issuer)
		check(err)
		folder := filepath.Join(root, "server", name)
		check(os.MkdirAll(folder, 0700))
		write(filepath.Join(folder, "cert.pem"), "CERTIFICATE", der, 0644)
		secret, err := x509.MarshalECPrivateKey(leafKey)
		check(err)
		write(filepath.Join(folder, "key.pem"), "EC PRIVATE KEY", secret, 0600)
		hash := sha256.Sum256(der)
		pins[name] = hex.EncodeToString(hash[:])
	}
	data, err := json.Marshal(pins)
	check(err)
	check(os.WriteFile(filepath.Join(public, "pins.json"), data, 0644))
}
