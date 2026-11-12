"""Regression tests for group tabs' raw voltage profiles and AHP detection counts."""
import unittest
import numpy as np
import pandas as pd
from neuron_compare.bulk import COLUMNS, export_frame, import_kinetics_csv, pairwise_statistics
from neuron_compare.group_waveform import group_landmarks, prototype_figure, significant_waveform_pairs
from neuron_compare.ahp_resolution import ahp_resolution_analysis


def row(i, group, resolved=True):
    r = dict.fromkeys(COLUMNS, np.nan)
    peak = 100. + i * 10
    threshold = -55. + group
    r.update({
        'File ID': f'cell{i}', 'Filename': f'cell{i}.abf',
        'Status': 'OK' if resolved else 'Partial',
        'Sweep': 1, 'Sampling Rate (Hz)': 10000.,
        'AP Location (ms)': peak, 'AP Onset (ms)': peak - 1.,
        'AP Rise 10% (ms)': peak - .8, 'AP Rise 90% (ms)': peak - .2,
        'AP Rise 10–90% (ms)': .6, 'AP Half rise (ms)': peak - .5,
        'AP Half fall (ms)': peak + .5, 'AP Half width (ms)': 1.,
        'AP Peak Vm (mV)': 35. + group,
        'AP threshold Vm (mV)': threshold,
        'AP Amplitude from AP threshold (mV)': 90.,
        'AHP Onset (ms)': peak + 1.,
        'AHP Half rise (ms)': peak + 1.5,
        'AHP Location (ms)': peak + 3. if resolved else np.nan,
        'AHP Trough Vm (mV)': -75. - group if resolved else np.nan,
        'AHP Amplitude from AP threshold (mV)': -20. - 2 * group if resolved else np.nan,
    })
    return r


class AHPResolutionWaveformTests(unittest.TestCase):
    def setUp(self):
        self.rows = [row(i, i // 3, resolved=(i not in (1, 3, 4))) for i in range(6)]
        self.groups = {'Control': ['cell0', 'cell1', 'cell2'],
                       'Drug': ['cell3', 'cell4', 'cell5']}

    def test_resolution_counts_and_fisher_for_sparse_2x2(self):
        fig, counts, stats = ahp_resolution_analysis(self.rows, self.groups)
        self.assertEqual(counts['Resolved'].tolist(), [2, 1])
        self.assertEqual(counts['Unresolved'].tolist(), [1, 2])
        self.assertTrue(np.isfinite(stats.iloc[0]['Chi-squared']))
        self.assertTrue(np.isfinite(stats.iloc[0]['Fisher exact p-value (2 groups)']))
        self.assertEqual(len(fig.data), 2)

    def test_missing_ap_excluded_and_missing_recovery_not_unresolved(self):
        rows = [dict(r) for r in self.rows]
        rows[0]['Status'] = 'Partial'   # no AHP recovery can still have trough
        rows[0]['AHP Half fall (ms)'] = np.nan
        rows[1]['Status'] = 'No AP'
        rows[1]['AP Location (ms)'] = np.nan
        _, counts, _ = ahp_resolution_analysis(rows, self.groups)
        self.assertEqual(counts.iloc[0]['Resolved'], 2)
        self.assertEqual(counts.iloc[0]['Unresolved'], 0)
        self.assertEqual(counts.iloc[0]['Excluded (no valid AP)'], 1)

    def test_undefined_all_resolved(self):
        rows = [row(i, i // 3) for i in range(6)]
        _, _, stats = ahp_resolution_analysis(rows, self.groups)
        self.assertTrue(np.isnan(stats.iloc[0]['p-value']))

    def test_raw_voltage_anchors_and_normalized_invariance(self):
        rows = [row(i, i // 3) for i in range(6)]
        raw = group_landmarks(rows, self.groups, voltage_mode='absolute')
        relative = group_landmarks(rows, self.groups, voltage_mode='relative')
        p = {label: y for x, y, label in raw['Control']}
        self.assertAlmostEqual(p['AP onset'], -55.)
        self.assertAlmostEqual(p['AP peak'], 35.)
        self.assertAlmostEqual(p['AHP trough'], -75.)
        self.assertAlmostEqual(dict((label, y) for x, y, label in relative['Control'])['AP peak'], 90.)
        for record in rows:
            record['AP Peak Vm (mV)'] += 10.
            record['AHP Trough Vm (mV)'] += 10.
        self.assertEqual(group_landmarks(rows, self.groups, voltage_mode='relative'), relative)

    def test_legacy_csv_has_no_raw_voltage_profile(self):
        rows = [row(i, i // 3) for i in range(6)]
        legacy = export_frame(rows).drop(columns=['AP peak Vm (mV)', 'AHP trough Vm (mV)'])
        imported, _ = import_kinetics_csv(legacy.to_csv(index=False).encode())
        ids = {'Control': [r['File ID'] for r in imported[:3]],
               'Drug': [r['File ID'] for r in imported[3:]]}
        self.assertFalse(group_landmarks(imported, ids, voltage_mode='absolute'))

    def test_absolute_significance_uses_raw_vm_measure_names(self):
        rows = [row(i, i // 3) for i in range(6)]
        tests = pairwise_statistics(rows, self.groups)
        figure = prototype_figure(rows, self.groups, tests, voltage_mode='absolute')
        self.assertEqual(figure.layout.meta['voltage_mode'], 'absolute')
        self.assertIn('Membrane potential (mV)', figure.layout.yaxis.title.text)
        self.assertIn('AHP trough Vm (mV)', tests['Measure'].tolist())


if __name__ == '__main__':
    unittest.main()
