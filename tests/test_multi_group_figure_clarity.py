"""Regressions for readable multiple-group comparisons and waveform significance."""
import unittest

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from matplotlib import pyplot as plt

from neuron_compare.bulk import SIGNIFICANCE_METHODS
from neuron_compare.group_figure import (
    _comparison_rows, _draw_combined_boxplots, standalone_waveform_png,
    combined_boxplots_png, combined_boxplots_pdf,
)
from neuron_compare.group_waveform import (
    prototype_figure, significant_waveform_pairs,
)
from neuron_compare.bulk import COLUMNS


def recording(index, group):
    row = dict.fromkeys(COLUMNS, np.nan)
    baseline = 100 + index * 10
    row.update({
        'File ID': f'cell{index}', 'Filename': f'cell{index}.abf',
        'Status': 'OK', 'Group': str(group), 'Sweep': 1,
        'Sampling Rate (Hz)': 50000,
        'AP Location (ms)': baseline,
        'AP Onset (ms)': baseline - .6,
        'AP Rise 10% (ms)': baseline - .5,
        'AP Rise 90% (ms)': baseline - .2,
        'AP Rise 10–90% (ms)': .3,
        'AP Half rise (ms)': baseline - .35,
        'AP Half fall (ms)': baseline + .4,
        'AP Half width (ms)': .75,
        'AHP Onset (ms)': baseline + .6,
        'AHP Half rise (ms)': baseline + 1.2,
        'AHP Location (ms)': baseline + 2,
        'AP Amplitude from AP threshold (mV)': 80 + group * 3 + index % 2,
        'AHP Amplitude from AP threshold (mV)': -(10 + group + index % 2),
    })
    return row


class FigureClarityTests(unittest.TestCase):
    def test_three_group_brackets_and_separate_stat_table(self):
        fig = go.Figure()
        for name, vals in (
            ("AL", [-.8, -.9, -.7]),
            ("FD", [-1., -1.2, -.8]),
            ("RF", [-.7, -.65, -.6]),
        ):
            fig.add_trace(go.Box(name=name, y=vals))
        fig.update_layout(title="AP Rise 10% (ms)", yaxis_title="AP Rise 10% (ms)")
        fig.add_shape(type="path", path="M 0 -0.45 L 0 -0.40 L 1 -0.40 L 1 -0.45")
        fig.add_annotation(x=.5, y=-.39, xref="x", yref="y", text="*")
        fig.add_annotation(
            x=.5, y=-.22, xref="paper", yref="paper",
            text=("AL vs FD: Welch p=0.025; BH FDR p=0.188; Holm p=0.431"
                  "<br>AL vs RF: Welch p=0.001; BH FDR p=0.010; Holm p=0.030"
                  "<br>FD vs RF: Welch p=0.051; BH FDR p=0.120; Holm p=0.210"),
        )
        self.assertEqual(len(_comparison_rows(fig)), 3)
        combined = _draw_combined_boxplots([fig])
        try:
            self.assertGreaterEqual(len(combined.axes), 2)
            box_axis, p_axis = combined.axes[:2]
            # Lines must reconstruct Plotly path coordinates (and not vanish).
            self.assertTrue(any(
                len(line.get_xdata()) == 4
                and np.allclose(line.get_xdata(), [1, 1, 2, 2])
                for line in box_axis.lines))
            self.assertEqual(len(p_axis.tables), 1)
            cells = p_axis.tables[0].get_celld()
            text = [cell.get_text().get_text() for cell in cells.values()]
            for label in ("AL vs FD", "AL vs RF", "FD vs RF", "Welch p", "BH FDR p", "Holm p"):
                self.assertIn(label, text)
        finally:
            plt.close(combined)
        self.assertTrue(combined_boxplots_png([fig], dpi=90).startswith(bytes([137, 80, 78, 71])))
        self.assertTrue(combined_boxplots_pdf([fig]).startswith(b"%PDF"))

    def test_three_group_waveform_identifies_significant_group_pairs(self):
        rows = [recording(i, i // 3) for i in range(9)]
        groups = {name: [f"cell{3*j+i}" for i in range(3)]
                  for j, name in enumerate(("AL", "FD", "RF"))}
        stats = pd.DataFrame([
            {"Measure": "AP Onset (ms)", "Group A": "AL", "Group B": "FD",
             "Welch p-value": .0001, "BH-adjusted p-value": .0003,
             "Holm-adjusted p-value": .0006},
            {"Measure": "AP amplitude (mV)", "Group A": "FD", "Group B": "RF",
             "Welch p-value": .003, "BH-adjusted p-value": .009,
             "Holm-adjusted p-value": .012},
            {"Measure": "AHP Location (ms)", "Group A": "AL", "Group B": "RF",
             "Welch p-value": .4, "BH-adjusted p-value": .7,
             "Holm-adjusted p-value": .9},
        ])
        pairs = significant_waveform_pairs(stats, groups)
        self.assertEqual(len(pairs), 2)
        self.assertEqual({(p["Group A"], p["Group B"]) for p in pairs},
                         {("AL", "FD"), ("FD", "RF")})
        figure = prototype_figure(rows, groups, stats)
        self.assertEqual(len([t for t in figure.data if t.type == "scatter"]), 6)
        tables = [trace for trace in figure.data if trace.type == "table"]
        self.assertEqual(len(tables), 1)
        self.assertIn("AL vs FD", tables[0].cells.values[1])
        self.assertIn("FD vs RF", tables[0].cells.values[1])
        self.assertGreater(len(standalone_waveform_png(figure, dpi=75)), 1000)

    def test_unadjusted_vs_corrected_visibility_is_consistent(self):
        groups = {"AL": ["1"], "FD": ["2"], "RF": ["3"]}
        tests = pd.DataFrame([{
            "Measure": "AP Onset (ms)", "Group A": "AL", "Group B": "RF",
            "Welch p-value": .03, "BH-adjusted p-value": .12,
            "Holm-adjusted p-value": .22,
        }])
        self.assertEqual(len(significant_waveform_pairs(tests, groups, "Holm-Bonferroni")), 0)
        self.assertEqual(len(significant_waveform_pairs(
            tests, groups, "Welch's t-test (uncorrected)")), 1)


if __name__ == "__main__":
    unittest.main()
