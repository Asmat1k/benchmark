# Initialize the network routes.
route_init() {
  docker run --rm --network "container:$(compose ps -q "$1")" --cap-drop ALL --cap-add NET_ADMIN wswt-bench-router:dev init "$2" "$3" "$4"
}
# Configure the benchmark network links.
setup_links() {
  for role in browser server; do
    case "$role" in
    browser)
      subnet=10
      peer=20
      ;;
    server)
      subnet=20
      peer=10
      ;;
    esac
    docker run --rm --cap-drop ALL --cap-add NET_ADMIN --cap-add SYS_PTRACE --network "container:$(compose ps -q router)" --pid "container:$(compose ps -q "$role")" wswt-bench-router:dev link "172.28.$subnet.2" "to_$role" >>"$run_dir/router-links.txt"
    route_init "$role" "172.28.$subnet.10" "172.28.$peer.10" "172.28.$subnet.2" >>"$run_dir/$role-route.txt"
  done
}
