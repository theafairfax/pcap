"""Regression tests for two timing exports and arbitrary group comparisons."""
import unittest
from unittest.mock import patch

import numpy as np
from neuron_compare.bulk import (
    analyze_file, export_frame, compare_multiple_groups, EXPORT_COLUMNS,
    EXPORT_TIMES, COMPARISON_COLUMNS,
)
from neuron_compare.recordings import Sweep


class BulkExportGroupTests(unittest.TestCase):
    def sample_rows(self):
        t = np.arange(0., .080, .00002)
        v = np.interp(t * 1000,
                      [0, 18, 19, 20, 21, 22.5, 28, 34, 80],
                      [-65, -65, -60, 30, -65, -77, -65, -60, -65])
        sweep = Sweep(0, t, v)
        with patch('neuron_compare.bulk.load_recording', return_value=[sweep]):
            first = analyze_file(b'data', 'a.abf')
        rows = []
        for i in range(3):
            row = dict(first)
            row['File ID'] = str(i)
            row['Filename'] = str(i) + '.abf'
            # Shift all event timestamps to ensure groups do not compare
            # absolute sweep locations.
            for key in ('AP Location (ms)', 'AP Onset (ms)',
                        'AP Rise 10% (ms)', 'AP Rise 90% (ms)',
                        'AP Half rise (ms)', 'AP Half fall (ms)',
                        'AHP Location (ms)', 'AHP Onset (ms)',
                        'AHP Half rise (ms)'):
                row[key] += 10. * i
            rows.append(row)
        return rows

    def test_absolute_relative_export_preserves_16_columns(self):
        rows = self.sample_rows()
        absolute = export_frame(rows)
        relative = export_frame(rows, relative=True)
        self.assertEqual(absolute.columns.tolist(), EXPORT_COLUMNS)
        self.assertEqual(relative.columns.tolist(), EXPORT_COLUMNS)
        self.assertAlmostEqual(absolute.loc[0, 'Sampling Rate (Hz)'], 50000., places=2)
        self.assertAlmostEqual(relative.loc[0, 'AP Location (ms)'], 0.)
        for column in EXPORT_TIMES:
            self.assertAlmostEqual(
                relative.loc[0, column],
                absolute.loc[0, column] - absolute.loc[0, 'AP Location (ms)'])
        for column in ('AP rise time (ms)', 'AP Half width (ms)',
                       'AP amplitude (mV)', 'AHP amplitude (mV)'):
            self.assertAlmostEqual(relative.loc[0, column], absolute.loc[0, column])
        self.assertGreater(absolute.loc[0, 'AHP amplitude (mV)'], 0.)
        self.assertLess(absolute.loc[0, 'AHP Half-Fall (ms)'],
                        absolute.loc[0, 'AHP Location (ms)'])

    def test_three_groups_and_missing_value(self):
        rows = self.sample_rows()
        rows[2]['AHP Half rise (ms)'] = np.nan
        fig, summary = compare_multiple_groups(
            rows, {'Group 1': ['0'], 'Group 2': ['1'], 'Group 3': ['2']})
        self.assertEqual(len(fig), len(COMPARISON_COLUMNS))
        times = fig[COMPARISON_COLUMNS.index('AP Onset (ms)')]
        self.assertEqual(len(times.data), 3)
        self.assertAlmostEqual(times.data[0].y[0], times.data[1].y[0])
        half = summary[summary['Measure'] == 'AHP Half-Fall (ms)']
        self.assertEqual(half['Missing'].tolist(), [0, 0, 1])

    def test_exclusive_assignment_validation(self):
        rows = self.sample_rows()
        with self.assertRaises(ValueError):
            compare_multiple_groups(rows, {'Group 1': ['0'], 'Group 2': ['0']})
        with self.assertRaises(ValueError):
            compare_multiple_groups(rows, {'Group 1': ['0'], 'Group 2': []})


if __name__ == '__main__':
    unittest.main()
