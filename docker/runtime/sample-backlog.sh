set -eu
while :; do
  stamp=$(awk '{printf "%.0f", $1*1000000}' /proc/uptime)
  tc -s -j qdisc show | jq -ce --argjson stamp "$stamp" '{usec:$stamp, queues:[.[] | select(.kind=="netem") | {dev,backlog,qlen,drops,limit:.options.limit}]} | select(.queues|length==2)'
  sleep 1
done
