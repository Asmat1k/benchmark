import argparse
import csv
import json
import shutil
import tempfile
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from measurement.raw import digest, read, rows, require, validate_hashes

MODES = ("WS", "WT-S", "WT-D")
COLORS = dict(zip(MODES, ("#0072B2", "#E69F00", "#009E73")))
METRICS = (("Q_ms", "p95 RTT (ms)"), ("S_pct", "On-time replies (%)"),
           ("U_pct", "No reply by horizon (%)"))
TITLES = {
    "comparison-rtt-ecdf": "RTT distribution",
    "comparison-q": "p95 RTT by run",
    "comparison-s": "On-time replies by run",
    "comparison-u": "Missing replies by run",
    "comparison-pairs": "Descriptive paired differences: WT-S minus WS",
    "comparison-send-lag": "Send lag distribution",
    "comparison-status": "All planned outcomes by transport",
}


# Return finite values without converting unavailable observations to zero.
def finite(values):
    return [float(v) for v in values if v is not None and np.isfinite(v)]


# Match complete WS and WT-S runs within the same block and profile.
def paired_values(items, profile, metric):
    blocks = {}
    for item in items:
        if item["profile"] == profile and item["mode"] in ("WS", "WT-S"):
            blocks.setdefault(item["attempt_id"], {})[item["mode"]] = item
    values = []
    for sides in blocks.values():
        if set(sides) != {"WS", "WT-S"}:
            continue
        if all(r["status"] == "complete" and r[metric] is not None for r in sides.values()):
            values.append(sides["WT-S"][metric] - sides["WS"][metric])
    return finite(values), len(blocks)


# Save the same figure in screen, vector, and print formats.
def save(figure, directory, name):
    figure.suptitle(TITLES[name])
    for suffix in ("png", "svg", "pdf"):
        figure.savefig(directory / f"{name}.{suffix}", dpi=160)
    plt.close(figure)


# Draw an empirical CDF and retain empty groups in the legend.
def ecdf(axis, values, label, color, linestyle="-"):
    values = sorted(finite(values))
    axis.step(values, np.arange(1, len(values) + 1) / max(1, len(values)),
              where="post", label=f"{label}: n={len(values)}", color=color,
              linestyle=linestyle)


# Collect all sent-slot lags from validated runs rather than only returned replies.
def lag_samples(series, items):
    result = {}
    for item in items:
        if item["status"] != "complete":
            continue
        artifact = next(a for a in item["artifacts"] if a["accepted"])
        folder = (series / artifact["path"]).resolve()
        require(folder.is_relative_to(series.resolve()), "foreign lag artifact")
        validate_hashes(folder)
        result[item["run_id"]] = finite(s["send_lag_ms"] for s in rows(folder / "slots.jsonl"))
    return result


# Build seven descriptive comparison figures without changing inference eligibility.
def figures(output, items, packets, lags):
    directory = output / "figures"
    directory.mkdir(exist_ok=True)
    profiles = sorted({r["profile"] for r in items})
    if not profiles:
        return
    for metric, label in METRICS:
        figure, axes = plt.subplots(1, len(profiles), figsize=(4 * len(profiles), 4),
                                    squeeze=False, layout="constrained")
        for axis, profile in zip(axes[0], profiles):
            for x, mode in enumerate(MODES):
                members = [r for r in items if r["profile"] == profile and r["mode"] == mode]
                values = finite(r[metric] for r in members if r["status"] == "complete")
                if values:
                    axis.boxplot([values], positions=[x], widths=.5, showfliers=False)
                    axis.scatter(x + np.linspace(-.12, .12, len(values)), values,
                                 color=COLORS[mode], s=16)
                observed_key = metric.replace("_ms", "_observed_ms").replace("_pct", "_observed_pct")
                partial = finite((r.get("observations") or {}).get(observed_key)
                                 for r in members if r["status"] != "complete")
                axis.scatter([x] * len(partial), partial, facecolors="none",
                             edgecolors=COLORS[mode], marker="D")
                axis.text(x, .98, f"{len(values)}/{len(members)} valid; {len(partial)} obs",
                          transform=axis.get_xaxis_transform(), ha="center", va="top", fontsize=7)
            axis.set(title=profile, ylabel=label, xticks=range(3), xticklabels=MODES)
            axis.margins(y=.22)
        save(figure, directory, "comparison-" + metric[0].lower())
    for name in ("comparison-rtt-ecdf", "comparison-send-lag"):
        figure, axes = plt.subplots(1, len(profiles), figsize=(4 * len(profiles), 4),
                                    squeeze=False, layout="constrained")
        for axis, profile in zip(axes[0], profiles):
            for mode in MODES:
                ids = {r["run_id"] for r in items if r["profile"] == profile and r["mode"] == mode}
                if name.endswith("send-lag"):
                    ecdf(axis, [v for run in ids for v in lags.get(run, [])], mode, COLORS[mode])
                else:
                    for accepted, style in ((True, "-"), (False, "--")):
                        sample = [r["rtt_ms"] for r in packets if r["run_id"] in ids
                                  and r["accepted"] == accepted and r["completed_by_horizon"]]
                        ecdf(axis, sample, mode + (" valid" if accepted else " observations"), COLORS[mode], style)
            if name.endswith("ecdf"):
                axis.axvline(100, color="gray", linestyle=":")
            axis.set(title=profile, ylabel="Fraction of observed samples",
                     xlabel="Send lag (ms), all sent slots in valid runs" if name.endswith("send-lag")
                     else "RTT (ms), replies within horizon")
            axis.legend(fontsize=6)
        save(figure, directory, name)
    figure, axes = plt.subplots(3, len(profiles), figsize=(4 * len(profiles), 9),
                                squeeze=False, layout="constrained")
    for row, (metric, label) in enumerate(METRICS):
        for axis, profile in zip(axes[row], profiles):
            values, planned = paired_values(items, profile, metric)
            axis.scatter(range(len(values)), values, color=COLORS["WT-S"], s=18)
            axis.axhline(0, color="gray", linestyle="--")
            axis.set(title=f"{profile}: {len(values)}/{planned} pairs", ylabel="Delta " + label,
                     xlabel="Available pair index; descriptive only")
    save(figure, directory, "comparison-pairs")
    statuses = sorted({r["status"] for r in items})
    figure, axes = plt.subplots(1, len(profiles), figsize=(4 * len(profiles), 4),
                                squeeze=False, layout="constrained")
    hatches = ("", "//", "xx", "..", "++", "oo", "**")
    for axis, profile in zip(axes[0], profiles):
        bottom = np.zeros(3)
        for status, hatch in zip(statuses, hatches):
            counts = [sum(r["profile"] == profile and r["mode"] == mode and r["status"] == status for r in items) for mode in MODES]
            axis.bar(MODES, counts, bottom=bottom, color=[COLORS[m] for m in MODES],
                     edgecolor="black", hatch=hatch, label=status)
            bottom += counts
        axis.set(title=profile, ylabel="Planned runs")
        axis.legend(fontsize=7)
    save(figure, directory, "comparison-status")


# Append comparison images and their interpretation limits to the final report.
def append_report(output):
    with (output / "report.md").open("a") as handle:
        handle.write("\n## Transport comparisons\n\nWS: blue; WT-S: orange; WT-D: green. Each network profile is separate.\n\n"
                     "Filled points: valid runs; hollow diamonds / dashed ECDF: unaccepted observations. "
                     "Counts show available/planned runs or pairs. Missing values are never zero. "
                     "RTT ECDF pools returned replies within the horizon (not equal-weight runs); "
                     "read it with S/U. The 100 ms RTT line is a reference: the actual deadline includes send lag. "
                     "Send-lag ECDF includes all sent slots in valid runs, including unanswered slots; partial runs are excluded. "
                     "Paired differences are descriptive only, without selected-pair tests or confidence intervals.\n")
        for name, title in TITLES.items():
            handle.write(f"\n### {title}\n\n![{title}](figures/{name}.png)\n")


# Verify a saved report before deriving a new, separate comparison report.
def verify_report(source):
    for line in (source / "SHA256SUMS").read_text().splitlines():
        sha, name = line.split("  ", 1)
        path = (source / name).resolve()
        require(path.is_relative_to(source.resolve()) and digest(path) == sha, "saved report hash mismatch")


# Extend a saved all-outcomes report without replacing any existing result.
def extend(series, output):
    series, output = series.resolve(), output.resolve()
    require(not output.exists(), "comparison output already exists")
    source = series / "derived"
    verify_report(source)
    data = read(source / "analysis.json")
    require(data["schedule_sha256"] == digest(series / "schedule.json"), "saved schedule changed")
    with (source / "rtt.csv").open() as handle:
        packets = list(csv.DictReader(handle))
    for packet in packets:
        for key in ("accepted", "completed_by_horizon"):
            require(packet[key] in ("True", "False"), "invalid packet boolean")
            packet[key] = packet[key] == "True"
        packet["rtt_ms"] = float(packet["rtt_ms"])
    lags = lag_samples(series, data["runs"])
    with tempfile.TemporaryDirectory(prefix=".comparisons-", dir=output.parent) as temporary:
        stage = Path(temporary) / "report"
        shutil.copytree(source, stage)
        figures(stage, data["runs"], packets, lags)
        append_report(stage)
        (stage / "comparison-provenance.json").write_text(json.dumps(dict(
            source_report_sha256=digest(source / "SHA256SUMS"),
            plotting_source_sha256=digest(Path(__file__)),
            inference="descriptive only; original analysis preserved"), indent=2) + "\n")
        (stage / "SHA256SUMS").write_text("".join(
            f"{digest(p)}  {p.relative_to(stage)}\n" for p in sorted(stage.rglob("*"))
            if p.is_file() and p.name != "SHA256SUMS"))
        require(not output.exists(), "comparison output already exists")
        stage.rename(output)
    return output


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("series", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    print(extend(args.series, args.output))
