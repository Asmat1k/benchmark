set -eu
actual=$(tc qdisc show dev "$1" | sed -nE '/^qdisc netem .* root /s/^.* seed ([0-9]+)([[:space:]].*)?$/\1/p')
test "$actual" = "$2" || {
  echo "Expected seed $2 on $1, kernel returned '$actual'" >&2
  exit 1
}
