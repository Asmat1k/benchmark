set -eu

device() {
    ip -o -4 addr show | awk -v addr="$1/24" '$4 == addr { sub(/@.*/, "", $2); print $2 }'
}
disable_offloads() {
    ethtool -K "$1" gro off gso off tso off lro off
    ethtool -k "$1" | awk '/^(generic-receive-offload|generic-segmentation-offload|tcp-segmentation-offload|large-receive-offload):/ { print; n++; if ($2 != "off") exit 1 } END { if (n != 4) exit 1 }'
    test "$(cat "/sys/class/net/$1/mtu")" = 1500
}
case "$1" in
link)
    iface=$(device "$2")
    ip addr del "$2/24" dev "$iface"
    ip link set "$iface" down
    ip link add "$3" type veth peer name bench0 netns 1
    ip link set "$3" up
    ip addr add "$2/24" dev "$3"
    disable_offloads "$3"
    ;;
init)
    iface=$(device "$2")
    if test -n "$iface"; then
        ip addr del "$2/24" dev "$iface"
        ip link set "$iface" down
    fi
    iface=bench0
    ip link set "$iface" up
    ip addr add "$2/24" dev "$iface"
    disable_offloads "$iface"
    ip route replace "$3/32" via "$4" dev "$iface"
    ip route get "$3"
    ;;
router)
    for addr in 172.28.10.2 172.28.20.2; do disable_offloads "$(device "$addr")"; done
    iptables -P FORWARD DROP
    iptables -A FORWARD -s 172.28.10.10 -d 172.28.20.10 -j ACCEPT
    iptables -A FORWARD -s 172.28.20.10 -d 172.28.10.10 -j ACCEPT
    exec sleep infinity
    ;;
profile)
    if [ "$2" = baseline ]; then delay=0; loss=0; else
    delay=$(jq -er --arg id "$2" '.profiles[] | select(.id==$id) | .egress_delay_ms' /profiles.json)
    loss=$(jq -er --arg id "$2" '.profiles[] | select(.id==$id) | .egress_loss_pct' /profiles.json)
    fi
    rate=$(jq -er .rate_mbit_s /profiles.json)
    limit=$(jq -er .limit_packets /profiles.json)
    jq -e '.mtu==1500 and .jitter_ms==0 and .correlation_pct==0' /profiles.json >/dev/null
    test "$3" != "$4"
    for addr in 172.28.20.2 172.28.10.2; do
        iface=$(device "$addr")
        seed=$3
        if test "$addr" = 172.28.10.2; then seed=$4; fi
        tc qdisc replace dev "$iface" root netem limit "$limit" delay "${delay}ms" loss random "${loss}%" rate "${rate}mbit" seed "$seed"
        sh /usr/local/bin/check-seed "$iface" "$seed"
        readback=$(tc -s -j qdisc show dev "$iface")
        printf '%s %s\n' "$addr" "$readback"
        echo "$readback" | jq -e --argjson delay "$delay" --argjson loss "$loss" --argjson rate "$rate" --argjson limit "$limit" '
          any(.[]; .kind=="netem" and .root and (.options |
            .limit==$limit and (.delay.delay // 0)==$delay/1000 and
            (.delay.jitter // 0)==0 and (.delay.correlation // 0)==0 and
            (."loss-random".loss // 0)==$loss/100 and (."loss-random".correlation // 0)==0 and
            .rate.rate==$rate*125000))
        ' >/dev/null
    done
    ;;
*) exit 2 ;;
esac
