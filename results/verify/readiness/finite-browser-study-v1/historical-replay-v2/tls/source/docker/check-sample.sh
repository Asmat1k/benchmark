set -eu
if [ "$1" = fresh ]; then
    target=$(awk '{printf "%.0f", $1*1000000-1500000}' /proc/uptime)
    attempts=1
else
    target=$1
    attempts=4
fi
for attempt in $(seq 1 "$attempts"); do
    if tail -1 /tmp/resources.jsonl | awk -v target="$target" -F '[:,]' '{for(i=1;i<NF;i++)if($i=="\"end_usec\"")end=$(i+1); if(end<target)exit 1; found=1; print} END {if(!found)exit 1}'; then exit 0; fi
    sleep 1
done
exit 1
