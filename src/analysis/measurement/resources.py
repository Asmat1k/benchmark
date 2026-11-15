from measurement.raw import require


# Validate resources.
def validate_resources(records, window):
    require(
        {r["role"] for r in records} == {"server", "browser", "router"},
        "incomplete resource roles",
    )
    for role in ("browser", "server", "router"):
        samples = [r for r in records if r["role"] == role]
        previous = None
        for index, sample in enumerate(samples):
            require(
                sample["sample_index"] == index
                and 0 < sample["interval_usec"] <= 1500000,
                "incomplete resource interval",
            )
            if previous is not None:
                require(
                    sample["end_usec"] - previous == sample["interval_usec"],
                    "incomplete resource gap",
                )
            require(sample["oom"] == 0, "resources OOM")
            if "cpu_start_lower_usec" in sample or "cpu_end_upper_usec" in sample:
                require(
                    0
                    <= sample["cpu_start_lower_usec"]
                    <= sample["end_usec"] - sample["interval_usec"]
                    and sample["cpu_end_upper_usec"] >= sample["end_usec"] + 10000,
                    "invalid CPU snapshot brackets",
                )
            previous = sample["end_usec"]
        require(
            samples[0]["end_usec"] - samples[0]["interval_usec"] <= window["start_usec"]
            and samples[-1]["end_usec"] >= window["end_usec"],
            "incomplete resource coverage",
        )
