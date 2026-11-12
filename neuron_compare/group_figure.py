"""Publication-friendly combined PNG/PDF group comparisons.

Boxplots, pairwise significance brackets, p-value tables and the waveform
significance key are reconstructed from the existing Plotly figures. Statistical
tests are not recalculated during export.
"""
from html import unescape
from io import BytesIO
import math
import re

import matplotlib
matplotlib.use("Agg")
from matplotlib import pyplot as plt
import numpy as np


def _plain_text(value):
    return unescape(re.sub(r"<[^>]+>", " ", str(value or ""))).strip()


def _comparison_rows(source):
    """Extract one row per group pair, avoiding overlapping multiline annotations."""
    rows = []
    for ann in source.layout.annotations or []:
        if ann.yref != "paper":
            continue
        # Plotly uses <br>; stripping all tags previously concatenated 15 pairs.
        for line in re.split(r"<br\s*/?>|\n", str(ann.text or ""), flags=re.IGNORECASE):
            line = _plain_text(line)
            match = re.match(
                r"^(.+?)\s+vs\s+(.+?):\s*Welch p=(.*?);\s*BH FDR p=(.*?);\s*Holm p=(.*)$",
                line,
            )
            if match:
                a, b, welch, bh, holm = match.groups()
                rows.append([a + " vs " + b, welch, bh, holm])
            elif line:
                # Also support older/free-form comparison captions.
                rows.append([line, "", "", ""])
    return rows


def _waveform_table(waveform):
    """Read the same significant-group-pair table shown in the interactive figure."""
    for trace in waveform.data:
        if trace.type == "table":
            headers = [_plain_text(value) for value in trace.header.values]
            columns = list(trace.cells.values)
            rows = [[_plain_text(column[i]) for column in columns]
                    for i in range(len(columns[0]))] if columns else []
            return headers, rows
    return [], []


def _draw_table(ax, headings, rows, widths=None):
    ax.set_axis_off()
    if not rows:
        return
    table = ax.table(cellText=rows, colLabels=headings, cellLoc="center",
                     colLoc="center", colWidths=widths, bbox=[0, 0, 1, 1])
    table.auto_set_font_size(False)
    longest = max((len(str(v)) for row in rows for v in row), default=0)
    table.set_fontsize(8 if longest > 40 else 9)
    for (r, c), cell in table.get_celld().items():
        cell.set_linewidth(.35)
        cell.set_edgecolor("#cbd5e1")
        if r == 0:
            cell.set_facecolor("#e2e8f0")
            cell.set_text_props(weight="bold", color="#334155")
        elif r % 2 == 0:
            cell.set_facecolor("#f8fafc")
        if c == 0:
            cell.get_text().set_ha("left")
    return table


def _draw_waveform(ax, waveform):
    """Recreate the landmark prototype (and its matching colors) in Matplotlib."""
    for trace in waveform.data:
        if trace.type == "table":
            continue
        x = np.asarray(trace.x, dtype=float)
        y = np.asarray(trace.y, dtype=float)
        color = (getattr(getattr(trace, "line", None), "color", None)
                 or getattr(getattr(trace, "marker", None), "color", None)
                 or "#475569")
        if trace.mode == "lines":
            ax.plot(x, y, color=color, linewidth=2.5, label=trace.name)
        elif trace.mode == "markers":
            ax.scatter(x, y, color=color, s=24, zorder=4)
    for ann in waveform.layout.annotations or []:
        if ann.xref in (None, "x") and ann.yref in (None, "y"):
            ax.text(float(ann.x), float(ann.y), _plain_text(ann.text),
                    fontsize=12, ha="center", fontweight="bold")
    ax.axvline(0, color="#94a3b8", linestyle="--", lw=.9)
    ax.axhline(0, color="#94a3b8", linestyle=":", lw=.9)
    mode = (getattr(waveform.layout, 'meta', None) or {}).get('voltage_mode', 'relative')
    ax.set_title("Raw membrane-voltage protowaveforms" if mode == "absolute"
                 else "Threshold-normalized protowaveforms",
                 fontsize=11, fontweight="bold", loc="left")
    ax.set_xlabel("Time from AP peak (ms)")
    ax.set_ylabel("Membrane potential (mV)" if mode == "absolute"
                  else "Relative to AP threshold (mV)")
    ax.grid(alpha=.18)
    ax.legend(fontsize=9, loc="best")
    ax.text(.5, -.21, "Schematic interpolation of mean landmarks; not averaged raw voltage traces.",
            transform=ax.transAxes, ha="center", va="top", fontsize=9, color="#64748b")


def standalone_waveform_png(waveform, dpi=200):
    headers, rows = _waveform_table(waveform)
    table_height = max(.7, .25 * (len(rows) + 1)) if rows else 0
    fig = plt.figure(figsize=(12, 6.8 + table_height))
    try:
        grid = fig.add_gridspec(2, 1, height_ratios=[5.3, table_height],
                                hspace=.42, left=.09, right=.96, top=.92, bottom=.06) if rows else None
        ax = fig.add_subplot(grid[0]) if rows else fig.add_subplot(111)
        _draw_waveform(ax, waveform)
        if rows:
            _draw_table(fig.add_subplot(grid[1]), headers, rows, widths=[.27, .47, .26])
        else:
            fig.subplots_adjust(bottom=.22)
        output = BytesIO()
        fig.savefig(output, format="png", dpi=dpi, bbox_inches="tight", facecolor="white")
        return output.getvalue()
    finally:
        plt.close(fig)


def _draw_boxplot(ax, source, index):
    """Preserve all group positions and draw Plotly path brackets at correct x values."""
    labels, colors, samples = [], [], []
    for trace in source.data:
        if trace.type != "box":
            continue
        values = np.asarray(trace.y if trace.y is not None else [], dtype=float)
        values = values[np.isfinite(values)]
        labels.append(str(trace.name))
        colors.append(getattr(getattr(trace, "line", None), "color", None) or "#475569")
        samples.append(values)
    positions = list(range(1, len(labels) + 1))
    for position, sample, color in zip(positions, samples, colors):
        if len(sample):
            box = ax.boxplot([sample], positions=[position], patch_artist=True,
                             showfliers=False, widths=.6)
            box["boxes"][0].set_facecolor(color)
            box["boxes"][0].set_edgecolor(color)
            box["boxes"][0].set_alpha(.62)
            box["medians"][0].set_color("#222222")
            rng = np.random.default_rng(2026 + index * 101 + position)
            ax.scatter(position + rng.uniform(-.15, .15, len(sample)), sample,
                       s=12, color=color, alpha=.85, edgecolors="white",
                       linewidths=.25, zorder=4)
        ax.text(position, -.17, "n=" + str(len(sample)), ha="center", va="top",
                transform=ax.get_xaxis_transform(), fontsize=9, color="#334155")
    ax.set_xlim(.45, max(1.55, len(labels) + .55))
    ax.set_xticks(positions, labels)
    ax.tick_params(axis="x", labelrotation=20, labelsize=9)
    title = _plain_text(source.layout.title.text).split("·")[0].strip()
    ax.set_title(title, fontsize=11, fontweight="bold", loc="left", pad=9)
    ax.set_ylabel(_plain_text(source.layout.yaxis.title.text), fontsize=9)
    ax.grid(axis="y", alpha=.2)

    # Plotly bracket paths are of the form "M 0 1 L 0 2 L 1 2 L 1 1".
    # The previous pattern escaped \s and \d twice, so it matched nothing.
    for shape in source.layout.shapes or []:
        if shape.type != "path" or not shape.path:
            continue
        coordinates = re.findall(r"[ML]\s*([-+\d.eE]+)\s+([-+\d.eE]+)", shape.path)
        if coordinates:
            x, y = zip(*[(float(x) + 1, float(y)) for x, y in coordinates])
            ax.plot(x, y, color="#334155", lw=1.15, zorder=6)
    for ann in source.layout.annotations or []:
        if ann.yref == "y":
            ax.text(float(ann.x) + 1, float(ann.y), _plain_text(ann.text),
                    ha="center", va="bottom", fontsize=10, fontweight="bold",
                    zorder=7)
    yrange = source.layout.yaxis.range
    if yrange is not None and len(yrange) == 2:
        ax.set_ylim(float(yrange[0]), float(yrange[1]))


def _draw_combined_boxplots(figures, columns=3, title="", waveform=None):
    """Reserve a dedicated, legible p-value table beneath EACH subplot."""
    if not figures:
        raise ValueError("No comparison plots to export.")
    parts = [(f, _comparison_rows(f)) for f in figures]
    if waveform is not None:
        _, waveform_rows = _waveform_table(waveform)
    else:
        waveform_rows = []
    maximum = max([len(x) for _, x in parts] + ([len(waveform_rows)] if waveform is not None else [0]))
    total = len(figures) + int(waveform is not None)
    cols = min(max(1, int(columns)), total)
    row_count = math.ceil(total / cols)
    # Scale each panel with the number of pairwise comparisons (up to 15
    # for six groups), keeping bracket space and the table independent.
    row_inches = 6.8 + .30 * maximum
    fig = plt.figure(figsize=(7.4 * cols, row_inches * row_count))
    outer = fig.add_gridspec(row_count, cols, left=.06, right=.985, bottom=.055,
                             top=.86 if title else .90, wspace=.30, hspace=.30)
    if title:
        fig.suptitle(str(title).strip(), fontsize=19, fontweight="bold",
                     x=.5, y=.984, ha="center", wrap=True)
    fig.text(.5, .917 if title else .958,
             "Time-based kinetic measurements (ms) are relative to the AP peak (t = 0 ms).",
             ha="center", va="top", fontsize=11, color="#475569")

    for index in range(total):
        is_waveform = index == len(figures)
        rows = waveform_rows if is_waveform else parts[index][1]
        # The second axes is a genuine table, not a text annotation floating
        # outside the plot. This prevents colliding footers across rows.
        table_height = max(.7, .25 * (len(rows) + 1)) if rows else .35
        inner = outer[index // cols, index % cols].subgridspec(
            2, 1, height_ratios=[5.0, table_height], hspace=.38)
        ax = fig.add_subplot(inner[0])
        if is_waveform:
            _draw_waveform(ax, waveform)
        else:
            _draw_boxplot(ax, figures[index], index)
        note_ax = fig.add_subplot(inner[1])
        if is_waveform:
            headers = _waveform_table(waveform)[0]
            _draw_table(note_ax, headers, rows, widths=[.27, .47, .26])
        else:
            _draw_table(note_ax, ["Comparison", "Welch p", "BH FDR p", "Holm p"],
                        rows, widths=[.46, .18, .18, .18])
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
    """Export raster master figure with brackets and all p-values."""
    return _combined_export(figures, "png", columns=columns, dpi=dpi, title=title, waveform=waveform)


def combined_boxplots_pdf(figures, columns=3, title="", waveform=None):
    """Export the same combined subplots as vector PDF."""
    return _combined_export(figures, "pdf", columns=columns, title=title, waveform=waveform)
