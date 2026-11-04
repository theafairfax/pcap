"""Export Plotly group comparisons to combined PNG/PDF using Matplotlib."""
from io import BytesIO
import math
import re
import matplotlib
matplotlib.use("Agg")
from matplotlib import pyplot as plt
import numpy as np


def _plain_text(value):
    return re.sub(r"<[^>]+>", " ", str(value or "")).replace("&lt;", "<").replace("&gt;", ">").strip()


def _draw_waveform(ax, waveform):
    """Draw the same landmark prototype in raster/vector exports."""
    for trace in waveform.data:
        x = np.asarray(trace.x, dtype=float)
        y = np.asarray(trace.y, dtype=float)
        color = getattr(getattr(trace, 'line', None), 'color', None) or getattr(getattr(trace, 'marker', None), 'color', None) or '#475569'
        if trace.mode == 'lines':
            ax.plot(x, y, color=color, linewidth=2.5, label=trace.name)
        elif trace.mode == 'markers':
            ax.scatter(x, y, color=color, s=24, zorder=4)
    for ann in waveform.layout.annotations or []:
        if ann.xref in (None,'x') and ann.yref in (None,'y'):
            ax.text(float(ann.x),float(ann.y),_plain_text(ann.text),
                    fontsize=12, ha='center', fontweight='bold')
    ax.axvline(0,color='#94a3b8',linestyle='--',lw=.9)
    ax.axhline(0,color='#94a3b8',linestyle=':',lw=.9)
    ax.set_title('Prototypical AP/AHP by group (mean landmarks)',fontsize=11,fontweight='bold',loc='left')
    ax.set_xlabel('Time from AP peak (ms)')
    ax.set_ylabel('Relative to AP threshold (mV)')
    ax.grid(alpha=.18)
    ax.legend(fontsize=9)
    ax.text(.5,-.22,'Schematic interpolation of mean landmarks; not averaged raw voltage traces.',
            transform=ax.transAxes,ha='center',va='top',fontsize=9,color='#64748b')


def standalone_waveform_png(waveform, dpi=200):
    fig, ax = plt.subplots(figsize=(12,7))
    try:
        _draw_waveform(ax, waveform)
        fig.subplots_adjust(bottom=.20)
        output=BytesIO()
        fig.savefig(output,format='png',dpi=dpi,bbox_inches='tight',facecolor='white')
        return output.getvalue()
    finally:
        plt.close(fig)


def _draw_combined_boxplots(figures, columns=3, title='', waveform=None):
    """Recreate the group boxes as an overview figure, preserving all p-values.

    The input figures already encode relative coordinates, names, colors and
    Welch/Holm comparisons. No reanalysis is done for the export.
    """
    if not figures:
        raise ValueError("No comparison plots to export.")
    total = len(figures) + (1 if waveform is not None else 0)
    cols = min(max(1, int(columns)), total)
    rows = math.ceil(total / cols)
    fig, axes = plt.subplots(rows, cols, figsize=(7.0 * cols, 6.1 * rows),
                             squeeze=False)
    fig.subplots_adjust(left=.07, right=.98, bottom=.07, top=.87 if title else .91,
                        wspace=.32, hspace=.72)
    if title:
        fig.suptitle(str(title).strip(), fontsize=19, fontweight="bold", x=.5,
                     y=.985, ha="center", wrap=True)
    fig.text(.5, .923 if title else .965,
             "Time-based kinetic measurements (ms) are relative to the AP peak (t = 0 ms).",
             ha="center", va="top", fontsize=11, color="#475569")
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
            # Count only finite values actually displayed for each metric.
            for position, sample in enumerate(samples, start=1):
                ax.text(position, -.13, f"n={len(sample)}", ha="center", va="top",
                        transform=ax.get_xaxis_transform(), fontsize=10, color="#334155")
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
            ax.text(.5, -.23, p_text, transform=ax.transAxes, fontsize=9,
                    color="#64748b", va="top", ha="center", clip_on=False)
    if waveform is not None:
        _draw_waveform(axes.flat[len(figures)], waveform)
    for ax in list(axes.flat)[total:]:
        ax.set_visible(False)
    return fig


def _combined_export(figures, fmt, columns=3, dpi=175, title="", waveform=None):
    fig = _draw_combined_boxplots(figures, columns=columns, title=title, waveform=waveform)
    buffer = BytesIO()
    try:
        fig.savefig(buffer, format=fmt, dpi=dpi, bbox_inches="tight",
                    facecolor="white", pad_inches=.4)
        return buffer.getvalue()
    finally:
        plt.close(fig)


def combined_boxplots_png(figures, columns=3, dpi=175, title="", waveform=None):
    """Export a raster master figure with significance brackets and all p-values."""
    return _combined_export(figures, "png", columns=columns, dpi=dpi, title=title, waveform=waveform)


def combined_boxplots_pdf(figures, columns=3, title="", waveform=None):
    """Export the same combined subplots as a vector PDF."""
    return _combined_export(figures, "pdf", columns=columns, title=title, waveform=waveform)

