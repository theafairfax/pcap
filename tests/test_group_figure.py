"""Regression coverage for the all-boxplots PNG export."""
import io
import unittest
import numpy as np
import plotly.graph_objects as go

from neuron_compare.group_figure import combined_boxplots_png


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

    def test_no_figures(self):
        with self.assertRaises(ValueError):
            combined_boxplots_png([])


if __name__ == '__main__':
    unittest.main()
