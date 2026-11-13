"""Regression tests for per-sweep RMP, AP onset Vm, and eight voltage panels."""
import unittest
from unittest.mock import patch

import numpy as np

from neuron_compare.bulk import (
    average_rmp, analyze_file, export_frame, import_kinetics_csv,
    compare_multiple_groups, COMPARISON_COLUMNS, VOLTAGE_MEASURE_ORDER,
)
from neuron_compare.core import Settings
from neuron_compare.recordings import Sweep


def make_sweeps():
    t = np.arange(0., .08, .00002)
    # First sweep has no spike and no injected current. Its baseline still
    # contributes using the common injection onset from the other sweeps.
    quiet = Sweep(0, t, np.full_like(t, -70.), np.zeros_like(t))
    spike = np.interp(t * 1000,
                      [0, 18, 19, 20, 21, 22.5, 28, 35, 80],
                      [-65, -65, -60, 30, -65, -77, -65, -65, -65])
    active = Sweep(1, t, spike, np.where((t >= .015) & (t < .055), 100., 0.))
    later = Sweep(2, t, np.full_like(t, -60.),
                  np.where((t >= .015) & (t < .055), 120., 0.))
    return [quiet, active, later]


class RMPAndOnsetTests(unittest.TestCase):
    def test_average_of_three_pre_injection_sweep_baselines(self):
        sweeps = make_sweeps()
        rmp, n = average_rmp(sweeps)
        self.assertEqual(n, 3)
        self.assertAlmostEqual(rmp, -65.)
        # Baseline is a mean of sweep means, not a mean of all traces.
        self.assertAlmostEqual(rmp, (-70. - 65. - 60.) / 3.)

    def test_no_known_injection_start_does_not_invent_rmp(self):
        sweeps = make_sweeps()
        for sweep in sweeps:
            sweep.current = None
        rmp, count = average_rmp(sweeps)
        self.assertTrue(np.isnan(rmp))
        self.assertEqual(count, 0)
        explicit, count = average_rmp(sweeps, Settings(start_ms=15.))
        self.assertEqual(count, 3)
        self.assertAlmostEqual(explicit, -65.)

    def test_real_analysis_and_both_csv_time_bases(self):
        sweeps = make_sweeps()
        with patch('neuron_compare.bulk.load_recording', return_value=sweeps):
            row = analyze_file(b'voltage', 'cell.abf')
        self.assertEqual(row['Sweep'], 1)
        self.assertAlmostEqual(row['Average RMP (mV)'], -65.)
        self.assertEqual(row['RMP sweeps used'], 3)
        self.assertAlmostEqual(row['AP Peak Vm (mV)'], 30.)
        self.assertAlmostEqual(row['AHP Trough Vm (mV)'], -77.)
        self.assertAlmostEqual(row['AP peak relative to avg RMP (mV)'], 95.)
        self.assertAlmostEqual(row['AHP trough relative to avg RMP (mV)'], -12.)
        self.assertTrue(np.isfinite(row['AP threshold Vm (mV)']))
        row['File ID'] = 'cell-1'
        absolute = export_frame([row])
        relative = export_frame([row], relative=True)
        for col in ('Average RMP (mV)', 'AP onset Vm (mV)',
                    'AP peak Vm (mV)', 'AHP trough Vm (mV)',
                    'AP peak relative to avg RMP (mV)',
                    'AHP trough relative to avg RMP (mV)', 'RMP sweeps used'):
            self.assertEqual(absolute.loc[0, col], relative.loc[0, col])
        self.assertAlmostEqual(absolute.loc[0, 'AP onset Vm (mV)'],
                               row['AP threshold Vm (mV)'])
        for exported in (absolute, relative):
            imported, _ = import_kinetics_csv(exported.to_csv(index=False).encode())
            restored = export_frame(imported).iloc[0]
            for col in ('Average RMP (mV)', 'AP onset Vm (mV)',
                        'AP peak relative to avg RMP (mV)',
                        'AHP trough relative to avg RMP (mV)'):
                self.assertAlmostEqual(restored[col], absolute.loc[0, col])

    def test_eight_voltage_plots_and_explicit_onset_titles(self):
        rows = []
        with patch('neuron_compare.bulk.load_recording', return_value=make_sweeps()):
            row = analyze_file(b'voltage', 'cell.abf')
        for i in range(4):
            item = dict(row)
            item['File ID'] = f'file{i}'
            item['Filename'] = f'file{i}.abf'
            item['Average RMP (mV)'] += i
            item['AP peak relative to avg RMP (mV)'] -= i
            item['AHP trough relative to avg RMP (mV)'] -= i
            rows.append(item)
        figures, _ = compare_multiple_groups(rows, {
            'Control': ['file0', 'file1'], 'Drug': ['file2', 'file3']
        })
        by_measure = {fig.layout.meta['measure']: fig for fig in figures}
        self.assertTrue(set(VOLTAGE_MEASURE_ORDER) <= set(COMPARISON_COLUMNS))
        self.assertEqual(len(VOLTAGE_MEASURE_ORDER), 8)
        self.assertIn('AP onset', by_measure['AP amplitude (mV)'].layout.title.text)
        self.assertIn('AP onset', by_measure['AHP amplitude (mV)'].layout.title.text)
        self.assertEqual(by_measure['Average RMP (mV)'].data[0].y[0], -65.)
        self.assertEqual(by_measure['AHP trough relative to avg RMP (mV)'].data[0].y[0], -12.)


if __name__ == '__main__':
    unittest.main()
