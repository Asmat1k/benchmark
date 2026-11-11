set -eu
cp /trust/ca.crt /usr/local/share/ca-certificates/bench.crt
update-ca-certificates >/dev/null
runuser -u pwuser -- mkdir -p /home/pwuser/.pki/nssdb
runuser -u pwuser -- certutil -N -d sql:/home/pwuser/.pki/nssdb --empty-password
runuser -u pwuser -- certutil -A -d sql:/home/pwuser/.pki/nssdb -n bench -t C,, -i /trust/ca.crt
exec runuser -u pwuser -- timeout -k 1 45 node /runner/dist/main.js
