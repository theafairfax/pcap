"""Export all Plotly comparison boxes into a single PNG without Chromium/Kaleido."""
from io import BytesIO
import math
import re
import matplotlib
matplotlib.use("Agg")
from matplotlib import pyplot as plt
import numpy as np


def _plain_text(value):
    return re.sub(r"<[^>]+>", " ", str(value or "")).replace("&lt;", "<").replace("&gt;", ">").strip()


def combined_boxplots_png(figures, columns=3, dpi=175):
    """Recreate the group boxes as an overview image, preserving p-value labels.

    The input figures already encode relative coordinates, names, colors and
    Welch/Holm comparisons. No reanalysis is done for the export.
    """
    if not figures:
        raise ValueError("No comparison plots to export.")
    cols = min(max(1, int(columns)), len(figures))
    rows = math.ceil(len(figures) / cols)
    fig, axes = plt.subplots(rows, cols, figsize=(6.0 * cols, 4.6 * rows),
                             squeeze=False, layout="constrained")
    for index, source in enumerate(figures):
        ax = axes.flat[index]
        samples = []
        labels = []
        colors = []
        for trace in source.data:
            vals = np.asarray(trace.y if trace.y is not None else [], dtype=float)
            vals = vals[np.isfinite(vals)]
            if vals.size:
                samples.append(vals)
                labels.append(str(trace.name))
                color = getattr(getattr(trace, "line", None), "color", None)
                colors.append(color or "#475569")
        if samples:
            drawn = ax.boxplot(samples, patch_artist=True,
                               showfliers=False, widths=.60)
            # Set tick labels separately for compatibility with both older
            # Matplotlib (labels=) and newer Matplotlib (tick_labels=).
            ax.set_xticks(range(1, len(labels) + 1))
            ax.set_xticklabels(labels)
            for patch, color in zip(drawn["boxes"], colors):
                patch.set_facecolor(color)
                patch.set_alpha(.62)
                patch.set_edgecolor(color)
            # Reproduce individual observations in the exported overview.
            for position, (sample, color) in enumerate(zip(samples, colors), start=1):
                rng = np.random.default_rng(2026 + index * 101 + position)
                jitter = rng.uniform(-.15, .15, len(sample))
                ax.scatter(position + jitter, sample, s=12, color=color,
                           alpha=.85, edgecolors="white", linewidths=.25, zorder=4)
            for median in drawn["medians"]:
                median.set_color("#222222")
            ax.tick_params(axis="x", labelrotation=18, labelsize=8)
        else:
            ax.text(.5, .5, "No finite measurements", ha="center", va="center",
                    transform=ax.transAxes)
        title = _plain_text(source.layout.title.text).split("  ")[0]
        # Plotly titles contain a smaller embedded sample-size subtitle.
        title = title.split("·")[0].strip()
        ax.set_title(title, fontsize=11, fontweight="bold", loc="left", pad=9)
        ax.set_ylabel(_plain_text(source.layout.yaxis.title.text), fontsize=8)
        ax.grid(axis="y", alpha=.2)
        # Bracket coordinates are stored as Plotly path shapes using data axes.
        for shape in source.layout.shapes or []:
            if shape.type == "path" and shape.path:
                coords = re.findall(r"[ML]\\s*([-+\\d.eE]+)\\s+([-+\\d.eE]+)", shape.path)
                if coords:
                    x, y = zip(*[(float(a) + 1, float(b)) for a, b in coords])
                    ax.plot(x, y, color="#334155", lw=1.15, zorder=5)
        for ann in source.layout.annotations or []:
            if ann.yref == "y":
                ax.text(float(ann.x) + 1, float(ann.y), _plain_text(ann.text),
                        ha="center", va="bottom", fontsize=9, fontweight="bold")
        yrange = source.layout.yaxis.range
        if yrange is not None and len(yrange) == 2:
            ax.set_ylim(float(yrange[0]), float(yrange[1]))
        annotations = [ann for ann in source.layout.annotations or [] if ann.yref == "paper"]
        if annotations:
            p_text = "\n".join(_plain_text(ann.text).replace("  ", " ").strip()
                               for ann in annotations)
            ax.text(.01, -.23, p_text, transform=ax.transAxes, fontsize=7,
                    va="top", ha="left", clip_on=False)
    for ax in list(axes.flat)[len(figures):]:
        ax.set_visible(False)
    buffer = BytesIO()
    fig.savefig(buffer, format="png", dpi=dpi, bbox_inches="tight",
                facecolor="white", pad_inches=.25)
    plt.close(fig)
    return buffer.getvalue()
