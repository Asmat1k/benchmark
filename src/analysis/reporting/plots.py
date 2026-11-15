import math
import hashlib
import json

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager
import numpy as np
import pandas as pd
import seaborn as sns

from measurement.raw import digest, write


# Write the report figures.
def figures(output, runs, rtts, profiles, thresholds):
    from reporting.analyze import csv_table, json_numbers

    folder = output / "figures"
    folder.mkdir()
    sns.set_theme(style="whitegrid", context="paper")
    plt.rcParams.update(
        {
            "svg.hashsalt": "wswt-analysis-v1",
            "font.family": "DejaVu Sans",
            "figure.dpi": 100,
        }
    )
    data = pd.DataFrame(runs)
    data.to_csv(folder / "runs-plot.csv", index=False, na_rep="NA")
    pd.DataFrame(rtts, columns=["run_id", "mode", "profile", "RTT_ms"]).to_csv(
        folder / "ecdf-plot.csv", index=False
    )
    csv_table(
        folder / "effects-plot.csv",
        [
            dict(
                profile=p["profile"],
                n=p["n"],
                theta_ms=p["theta_ms"],
                Q_low_ms=p["CI9875"]["bounds"][0] if p["CI9875"] else None,
                Q_high_ms=p["CI9875"]["bounds"][1] if p["CI9875"] else None,
                mean_delta_S_pp=p["fullness"]["estimate"] if p["fullness"] else None,
                S_low_pp=p["fullness"]["bounds"][0] if p["fullness"] else None,
                S_high_pp=p["fullness"]["bounds"][1] if p["fullness"] else None,
            )
            for p in profiles
        ],
    )
    modes = list(dict.fromkeys(r["mode"] for r in runs))
    colors = dict(zip(("WS", "WT-S", "WT-D"), sns.color_palette("colorblind", 3)))
    spec = dict(
        backend=matplotlib.get_backend(),
        png_dpi=300,
        size_inches=[12, 8],
        font_sha256=digest(
            __import__("pathlib").Path(font_manager.findfont("DejaVu Sans"))
        ),
        rcParams={k: str(v) for k, v in plt.rcParams.items()},
        figures=[],
        infinity_policy="Text labels for infinite bounds; no finite substitution.",
        null_policy="NA counts shown; missing latency is not zero.",
    )
    spec["style_sha256"] = hashlib.sha256(
        json.dumps(spec["rcParams"], sort_keys=True).encode()
    ).hexdigest()

    # Save the supplied data.
    def save(fig, name):
        fig.tight_layout()
        for extension in ("png", "svg", "pdf"):
            metadata = (
                {"Date": None}
                if extension == "svg"
                else {"CreationDate": None, "ModDate": None}
                if extension == "pdf"
                else {}
            )
            fig.savefig(folder / f"{name}.{extension}", dpi=300, metadata=metadata)
        spec["figures"].append(
            dict(name=name, size_inches=fig.get_size_inches().tolist())
        )
        plt.close(fig)

    for metric, label, line in (
        ("Q_ms", "Conditional run Q (ms)", None),
        ("S_pct", "On-time slots S (%)", None),
        ("U_pct", "Uncompleted slots U (%)", thresholds["max_uncompleted_pct"]),
    ):
        fig, axes = plt.subplots(2, 2, figsize=(12, 8))
        for ax, profile in zip(axes.flat, profiles):
            for m, mode in enumerate(modes):
                group = data[
                    (data.profile == profile["profile"]) & (data["mode"] == mode)
                ]
                values = group[metric].dropna()
                ax.scatter(np.full(len(values), m), values, color=colors[mode], s=25)
                ax.text(
                    m,
                    0.98,
                    f"n={len(group)}, NA={len(group) - len(values)}",
                    transform=ax.get_xaxis_transform(),
                    ha="center",
                    va="top",
                    fontsize=8,
                )
            if line is not None:
                ax.axhline(
                    line, color="black", linestyle="--", label=f"U barrier {line}%"
                )
            ax.set(
                xticks=range(len(modes)),
                xticklabels=modes,
                title=profile["profile"],
                ylabel=label,
            )
        fig.suptitle(
            f"{label}; slots/run {sorted(set(data.count_planned))}; deadline {thresholds['deadline_ms']} ms, horizon {thresholds['horizon_ms']} ms"
        )
        save(fig, metric)
    for grouping in ("run_order", "session_id"):
        fig, axes = plt.subplots(3, 1, figsize=(12, 8))
        for ax, metric, label in zip(
            axes, ("Q_ms", "S_pct", "U_pct"), ("Q (ms)", "S (%)", "U (%)")
        ):
            for mode in modes:
                group = data[data["mode"] == mode]
                ax.scatter(
                    group[grouping], group[metric], label=mode, color=colors[mode], s=15
                )
            ax.set(ylabel=label, xlabel=grouping)
            ax.legend()
            if metric == "U_pct":
                ax.axhline(
                    thresholds["max_uncompleted_pct"], color="black", linestyle="--"
                )
        fig.suptitle(
            f"Run/session diagnostics; n={len(runs)}, Q NA={data.Q_ms.isna().sum()}; no pooled inference"
        )
        save(fig, grouping)
    fig, axes = plt.subplots(2, 2, figsize=(12, 8))
    for ax, profile in zip(axes.flat, profiles):
        for mode in modes:
            values = sorted(
                r["RTT_ms"]
                for r in rtts
                if r["profile"] == profile["profile"] and r["mode"] == mode
            )
            group = data[(data.profile == profile["profile"]) & (data["mode"] == mode)]
            planned = int(group.count_planned.sum())
            if values:
                ax.step(
                    values,
                    np.arange(1, len(values) + 1) / len(values),
                    where="post",
                    color=colors[mode],
                    label=f"{mode}: completed n={len(values)}/{planned} slots",
                )
            else:
                ax.plot([], [], color=colors[mode], label=f"{mode}: NA, n=0/{planned}")
        ax.set(
            title=profile["profile"],
            xlabel="Completed RTT (ms)",
            ylabel="Conditional ECDF",
        )
        ax.legend(fontsize=7)
    fig.suptitle(
        f"Descriptive ECDF conditional on completion by plan+{thresholds['horizon_ms']} ms; no message-level inference"
    )
    save(fig, "conditional-ecdf")
    fig, axes = plt.subplots(1, 2, figsize=(12, 5))
    for axis, key, unit, margin in (
        (
            axes[0],
            "CI9875",
            "Median paired Q difference (ms)",
            thresholds["practical_ms"],
        ),
        (
            axes[1],
            "fullness",
            "Mean paired S difference (pp)",
            thresholds["fullness_tolerance_pp"],
        ),
    ):
        for i, p in enumerate(profiles):
            item = p[key]
            if item is None:
                axis.text(0, i, "unavailable", ha="center")
                continue
            low, high = item["bounds"]
            estimate = p["theta_ms"] if key == "CI9875" else item["estimate"]
            axis.plot(estimate, i, "o", color="black")
            if math.isfinite(low) and math.isfinite(high):
                axis.plot([low, high], [i, i], color="black")
            else:
                axis.text(
                    0.02,
                    i + 0.1,
                    "CI: −∞ to +∞",
                    transform=axis.get_yaxis_transform(),
                    fontsize=8,
                )
        axis.axvline(-margin, color="red", linestyle="--")
        axis.axvline(margin, color="red", linestyle="--")
        axis.set(
            yticks=range(4),
            yticklabels=[f"{p['profile']} (n={p['n']})" for p in profiles],
            xlabel=unit,
        )
    fig.suptitle(
        "98.75% intervals; WT-S minus WS; dashed practical/fullness thresholds"
    )
    save(fig, "paired-effects")
    if "WT-D" in modes:
        csv_table(
            folder / "WT-D-plot.csv",
            [
                dict(
                    profile=p["profile"],
                    metric=key,
                    n=p.get("WT_D", {}).get("n", 0),
                    n_null_Q=p.get("WT_D", {}).get("n_null_Q", 0),
                    estimate=p.get("WT_D", {}).get(key, {}).get("estimate")
                    if p.get("WT_D", {}).get(key)
                    else None,
                    low=p["WT_D"][key]["bounds"][0]
                    if p.get("WT_D", {}).get(key)
                    else None,
                    high=p["WT_D"][key]["bounds"][1]
                    if p.get("WT_D", {}).get(key)
                    else None,
                )
                for p in profiles
                for key in ("Q", "S")
            ],
        )
        fig, axes = plt.subplots(1, 2, figsize=(12, 5))
        for axis, key, label in (
            (axes[0], "Q", "Median run Q (ms)"),
            (axes[1], "S", "Mean run S (%)"),
        ):
            for i, p in enumerate(profiles):
                descriptive = p.get("WT_D", {})
                interval = descriptive.get(key)
                if interval is None:
                    axis.text(0, i, "unavailable Q" if key == "Q" else "unavailable S")
                else:
                    axis.plot(interval["bounds"], [i, i], color="black")
                    axis.plot(interval["estimate"], i, "o", color="black")
            axis.set(
                yticks=range(4),
                yticklabels=[
                    f"{p['profile']} n={p.get('WT_D', {}).get('n', 0)}, Q NA={p.get('WT_D', {}).get('n_null_Q', 0)}"
                    for p in profiles
                ],
                xlabel=label,
            )
        fig.suptitle(
            "WT-D descriptive 95% block bootstrap intervals; Q conditional on completion, read with S"
        )
        save(fig, "WT-D-descriptive")
    write(folder / "plot-spec.json", json_numbers(spec))
