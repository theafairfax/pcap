"""Regression coverage for the all-boxplots PNG export."""
import io
import unittest
import numpy as np
import plotly.graph_objects as go

from neuron_compare.group_figure import (combined_boxplots_png, combined_boxplots_pdf,
                                         _draw_combined_boxplots)
from matplotlib import pyplot as plt


class GroupFigureTests(unittest.TestCase):
    def test_png_contains_all_plots(self):
        figures = []
        for metric in ('AP Half width (ms)', 'AHP amplitude (mV)', 'AP rise time (ms)'):
            fig = go.Figure()
            fig.add_trace(go.Box(name='Control', y=[1.0, 2.0, 3.0],
                                 line=dict(color='#475569')))
            fig.add_trace(go.Box(name='Drug', y=[2.0, 3.0, 4.0],
                                 line=dict(color='#dc645b')))
            fig.update_layout(title=metric + '<br><sup>Control n=3 · Drug n=3</sup>',
                              yaxis_title=metric)
            fig.add_annotation(x=.5, y=1.1, xref='paper', yref='paper',
                               text='Control vs Drug: p=0.200, Holm=0.600')
            figures.append(fig)
        png = combined_boxplots_png(figures, columns=2, dpi=90)
        self.assertTrue(png.startswith(b'\x89PNG\r\n\x1a\n'))
        self.assertGreater(len(png), 10000)
        pdf = combined_boxplots_pdf(figures, columns=2)
        self.assertTrue(pdf.startswith(b'%PDF-'))
        self.assertGreater(len(pdf), 1000)

    def test_export_title_description_counts_and_stat_placement(self):
        fig = go.Figure()
        fig.add_trace(go.Box(name='Control', y=[1., 2., np.nan]))
        fig.add_trace(go.Box(name='Drug', y=[3., 4., 5.]))
        fig.update_layout(title='AP amplitude (mV)', yaxis_title='AP amplitude (mV)')
        fig.add_annotation(x=.5, y=-.22, xref='paper', yref='paper',
                           text='Control vs Drug: Welch p=0.01; BH FDR p=0.02; Holm p=0.03')
        combined = _draw_combined_boxplots([fig], title='Nifedipine experiment')
        try:
            self.assertEqual(combined._suptitle.get_text(), 'Nifedipine experiment')
            self.assertTrue(any('t = 0 ms' in t.get_text() for t in combined.texts))
            axis = combined.axes[0]
            self.assertIn('n=2', [t.get_text() for t in axis.texts])
            self.assertIn('n=3', [t.get_text() for t in axis.texts])
            # Each panel now has its own independent p-value TABLE axes.
            table_axes = combined.axes[1]
            self.assertTrue(table_axes.tables)
            cells = table_axes.tables[0].get_celld()
            table_text = [cell.get_text().get_text() for cell in cells.values()]
            self.assertIn('Control vs Drug', table_text)
            self.assertIn('0.01', table_text)
            self.assertIn('0.02', table_text)
            self.assertIn('0.03', table_text)
        finally:
            plt.close(combined)
        png = combined_boxplots_png([fig], title='Nifedipine experiment', dpi=90)
        pdf = combined_boxplots_pdf([fig], title='Nifedipine experiment')
        self.assertTrue(png.startswith(bytes((137, 80, 78, 71))))
        self.assertTrue(pdf.startswith(b'%PDF-'))

    def test_no_figures(self):
        with self.assertRaises(ValueError):
            combined_boxplots_png([])


if __name__ == '__main__':
    unittest.main()
