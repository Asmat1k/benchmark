for role in browser server; do
  case "$role" in browser) subnet=10 ;; server) subnet=20 ;; esac
  endpoint_mac=$(compose exec -T "$role" cat /sys/class/net/bench0/address)
  router_mac=$(compose exec -T router cat "/sys/class/net/to_$role/address")
  compose exec -T router ip neigh replace "172.28.$subnet.10" lladdr "$endpoint_mac" nud permanent dev "to_$role"
  docker run --rm --cap-drop ALL --cap-add NET_ADMIN --network "container:$(compose ps -q "$role")" --entrypoint ip wswt-bench-router:dev neigh replace "172.28.$subnet.2" lladdr "$router_mac" nud permanent dev bench0
  compose exec -T router ip -j neigh show dev "to_$role" >"$run_dir/router-$role-neighbors.json"
  docker run --rm --cap-drop ALL --network "container:$(compose ps -q "$role")" --entrypoint ip wswt-bench-router:dev -j neigh show dev bench0 >"$run_dir/$role-neighbors.json"
done
