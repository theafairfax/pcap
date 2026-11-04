"""Optional grouped CSV workflow and landmark profile regression tests."""
import unittest
import numpy as np
from neuron_compare.bulk import (COLUMNS, EXPORT_COLUMNS, export_frame,
                                 import_kinetics_csv, pairwise_statistics)
from neuron_compare.group_waveform import group_landmarks, prototype_figure
from neuron_compare.group_figure import combined_boxplots_png, standalone_waveform_png
import plotly.graph_objects as go


def example(i, group):
    r = dict.fromkeys(COLUMNS, np.nan)
    r.update({
        'File ID': 'cell'+str(i), 'Filename': f'cell{i}.abf', 'Status': 'OK',
        'Group': str(group), 'Sweep': 1, 'Sampling Rate (Hz)': 50000,
        'AP Location (ms)': 100+i*10, 'AP Onset (ms)': 99.5+i*10,
        'AP Rise 10% (ms)': 99.6+i*10, 'AP Rise 90% (ms)': 99.8+i*10,
        'AP Rise 10–90% (ms)': .2, 'AP Half rise (ms)': 99.7+i*10,
        'AP Half fall (ms)': 100.4+i*10, 'AP Half width (ms)': .7,
        'AHP Onset (ms)': 100.6+i*10, 'AHP Half rise (ms)': 101+i*10,
        'AHP Location (ms)': 102+i*10,
        'AP Amplitude from AP threshold (mV)': 90+20*group+i%2,
        'AHP Amplitude from AP threshold (mV)': -(12+5*group+i%2),
    })
    return r


class GroupedWaveformTests(unittest.TestCase):
    def setUp(self):
        self.rows=[example(i, i//3) for i in range(6)]
        self.groups={'Control':[f'cell{i}' for i in range(3)],
                     'Treatment':[f'cell{i}' for i in range(3,6)]}

    def test_legacy_csv_unchanged_and_optional_group_roundtrip(self):
        legacy=export_frame(self.rows)
        self.assertEqual(legacy.columns.tolist(), EXPORT_COLUMNS)
        grouped=export_frame(self.rows,relative=True,include_groups=True)
        self.assertEqual(grouped.columns[1], 'Group')
        self.assertEqual(grouped['Group'].tolist(), ['0']*3+['1']*3)
        imported,basis=import_kinetics_csv(grouped.to_csv(index=False).encode())
        self.assertEqual(basis,'Relative')
        self.assertEqual([r['Group'] for r in imported], ['0']*3+['1']*3)
        self.assertEqual(len(export_frame(imported).columns),16)
        grouped.loc[0,'Group']='other'
        with self.assertRaisesRegex(ValueError,'Group must'):
            import_kinetics_csv(grouped.to_csv(index=False).encode())

    def test_mean_landmarks_and_voltage_scale(self):
        profiles=group_landmarks(self.rows,self.groups)
        self.assertEqual(set(profiles),set(self.groups))
        control=dict((p[2],p) for p in profiles['Control'])
        self.assertAlmostEqual(control['AP peak'][0],0)
        self.assertAlmostEqual(control['AP peak'][1],np.mean([90,91,90]))
        self.assertAlmostEqual(control['AHP trough'][1],-np.mean([12,13,12]))
        self.assertAlmostEqual(control['AP onset'][0],-.5)

    def test_prototype_exports(self):
        tests=pairwise_statistics(self.rows,self.groups)
        fig=prototype_figure(self.rows,self.groups,tests)
        self.assertEqual(len(fig.data),4)
        self.assertGreater(len(standalone_waveform_png(fig)),500)
        box=go.Figure(go.Box(y=[1,2,3], name='Control'))
        box.update_layout(title='AP Half width (ms)', yaxis_title='AP Half width (ms)')
        self.assertGreater(len(combined_boxplots_png([box],waveform=fig)),500)


if __name__=='__main__':
    unittest.main()
