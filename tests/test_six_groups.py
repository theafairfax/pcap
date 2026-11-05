"""Regression coverage for optional six-group PCAP exports and comparisons."""
import unittest
import numpy as np
from neuron_compare.bulk import (
    COLUMNS, COMPARISON_COLUMNS, export_frame, import_kinetics_csv,
    compare_multiple_groups, pairwise_statistics,
)
from neuron_compare.group_waveform import prototype_figure, group_landmarks


def recording(index, group):
    row = dict.fromkeys(COLUMNS, np.nan)
    baseline = 100. + index * 10
    row.update({
        'File ID': f'cell{index}', 'Filename': f'cell{index}.abf',
        'Status': 'OK', 'Group': str(group), 'Sweep': 1,
        'Sampling Rate (Hz)': 50000.,
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
        'AHP Location (ms)': baseline + 2.,
        'AP Amplitude from AP threshold (mV)': 80. + group * 3 + index % 2,
        'AHP Amplitude from AP threshold (mV)': -(10. + group + index % 2),
    })
    return row


class SixGroupTests(unittest.TestCase):
    def setUp(self):
        self.rows = [recording(i, i // 3) for i in range(18)]
        self.groups = {f'Group {j+1}': [f'cell{i}' for i in range(j*3, j*3+3)]
                       for j in range(6)}

    def test_six_group_csv_round_trip(self):
        exported = export_frame(self.rows, relative=True, include_groups=True)
        self.assertEqual(exported['Group'].tolist(), [str(i//3) for i in range(18)])
        imported, basis = import_kinetics_csv(exported.to_csv(index=False).encode())
        self.assertEqual(basis, 'Relative')
        self.assertEqual([row['Group'] for row in imported],
                         [str(i//3) for i in range(18)])
        exported.loc[0, 'Group'] = '6'
        with self.assertRaisesRegex(ValueError, 'Group must'):
            import_kinetics_csv(exported.to_csv(index=False).encode())

    def test_all_six_groups_have_pairwise_tests_and_overlaid_waveforms(self):
        tests = pairwise_statistics(self.rows, self.groups)
        self.assertEqual(len(tests), len(COMPARISON_COLUMNS) * 15)
        figures, summary = compare_multiple_groups(self.rows, self.groups)
        self.assertEqual(len(figures), len(COMPARISON_COLUMNS))
        self.assertTrue(all(len(fig.data) == 6 for fig in figures))
        self.assertEqual(len(summary), len(COMPARISON_COLUMNS) * 6)
        profiles = group_landmarks(self.rows, self.groups)
        self.assertEqual(len(profiles), 6)
        waveform = prototype_figure(self.rows, self.groups, tests)
        self.assertEqual(len(waveform.data), 12)
        self.assertEqual([trace.name for trace in waveform.data if trace.mode == 'lines'],
                         list(self.groups))

    def test_group_limit_and_exclusive_assignment(self):
        rows = self.rows + [recording(18, 6)]
        groups = {**self.groups, 'Group 7': ['cell18']}
        with self.assertRaisesRegex(ValueError, '2–6'):
            compare_multiple_groups(rows, groups)
        with self.assertRaisesRegex(ValueError, 'only be assigned to one'):
            compare_multiple_groups(self.rows, {
                'Control': ['cell0'], 'Drug': ['cell0'],
            })


if __name__ == '__main__':
    unittest.main()
