# Offline fixtures

`leaf.pem` is a self-signed synthetic certificate for `bench.test`, valid from
2026-11-01 through 2036-11-01. It is used only for certificate parsing, pin hashing
and fixed-date validity checks. No private key or trusted CA is stored here.

`tests.support.create_template` creates the remaining raw records and collector
files in the caller's temporary directory. Their clocks, identities and resource
observations are explicit synthetic values; they are not evidence of a network
measurement. Configuration and dependency bindings use the current repository.
