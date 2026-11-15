set -eu
cd /sys/fs/cgroup
# Collect the current resource sample.
snapshot() {
  cut -d' ' -f1 /proc/uptime
  awk '/^usage_usec |^throttled_usec / {print $2}' cpu.stat | tr '\n' ' '
  cat memory.current
  awk '$1=="oom" {print $2}' memory.events
  cut -d' ' -f1 /proc/uptime
}
set -- $(snapshot)
usage=$2
throttled=$3
oom=$5
previous=$6
previous_before=$1
index=0
while sleep 1; do
  set -- $(snapshot)
  awk -v sample_index="$index" -v role="$ROLE" -v run="$RUN_ID" -v previous="$previous" -v now="$6" -v lower="$previous_before" -v cpu="$(($2 - usage))" -v throttle="$(($3 - throttled))" -v mem="$4" -v oom="$(($5 - oom))" 'BEGIN {printf "{\"schema_version\":1,\"run_id\":\"%s\",\"role\":\"%s\",\"sample_index\":%d,\"end_usec\":%.0f,\"interval_usec\":%.0f,\"cpu_start_lower_usec\":%.0f,\"cpu_end_upper_usec\":%.0f,\"cpu_usage_usec\":%d,\"throttled_usec\":%d,\"memory_current\":%.0f,\"oom\":%d}\n",run,role,sample_index,now*1000000,(now-previous)*1000000,lower*1000000,now*1000000+10000,cpu,throttle,mem,oom}'
  index=$((index + 1))
  usage=$2
  throttled=$3
  oom=$5
  previous=$6
  previous_before=$1
done
