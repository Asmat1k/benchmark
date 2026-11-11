set -eu
cd /sys/fs/cgroup
snapshot() {
    awk '/^usage_usec |^throttled_usec / {print $2}' cpu.stat | tr '\n' ' '
    cat memory.current
    awk '$1=="oom" {print $2}' memory.events
    cut -d' ' -f1 /proc/uptime
}
set -- $(snapshot)
usage=$1; throttled=$2; oom=$4; previous=$5
index=0
while sleep 1; do
    set -- $(snapshot)
    awk -v sample_index="$index" -v role="$ROLE" -v run="$RUN_ID" -v previous="$previous" -v now="$5" -v cpu="$(($1-usage))" -v throttle="$(($2-throttled))" -v mem="$3" -v oom="$(($4-oom))" 'BEGIN {printf "{\"schema_version\":1,\"run_id\":\"%s\",\"role\":\"%s\",\"sample_index\":%d,\"end_usec\":%.0f,\"interval_usec\":%.0f,\"cpu_usage_usec\":%d,\"throttled_usec\":%d,\"memory_current\":%.0f,\"oom\":%d}\n",run,role,sample_index,now*1000000,(now-previous)*1000000,cpu,throttle,mem,oom}'
    index=$((index+1))
    usage=$1; throttled=$2; oom=$4; previous=$5
done
