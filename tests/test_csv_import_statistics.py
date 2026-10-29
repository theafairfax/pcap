"""Saved bulk CSV import and statistical comparison regression tests."""
import unittest
import numpy as np
from neuron_compare.bulk import (
    COLUMNS, export_frame, import_kinetics_csv, compare_multiple_groups,
    pairwise_statistics, COMPARISON_COLUMNS, EXPORT_COLUMNS,
)


def make_row(index, offset=0.):
    record = dict.fromkeys(COLUMNS, np.nan)
    record.update({
        'File ID': 'file' + str(index),
        'Filename': 'neuron_' + str(index) + '.abf',
        'Status': 'OK', 'Sweep': 3, 'Sampling Rate (Hz)': 50000.,
        'AP Location (ms)': 250. + offset,
        'AP Onset (ms)': 249.5 + offset,
        'AP Rise 10% (ms)': 249.6 + offset,
        'AP Rise 90% (ms)': 249.8 + offset,
        'AP Rise 10–90% (ms)': .2,
        'AP Half rise (ms)': 249.7 + offset,
        'AP Half fall (ms)': 250.3 + offset,
        'AP Half width (ms)': .6,
        'AHP Location (ms)': 252. + offset,
        'AHP Onset (ms)': 250.5 + offset,
        'AHP Half rise (ms)': 251. + offset,
        'AP Amplitude from AP threshold (mV)': 90. + index,
        'AHP Amplitude from AP threshold (mV)': -(15. + index),
    })
    return record


class SavedResultsTests(unittest.TestCase):
    def test_roundtrip_absolute_and_relative(self):
        originals = [make_row(0), make_row(1, offset=25.)]
        for basis in ('Absolute', 'Relative'):
            exported = export_frame(originals, relative=(basis == 'Relative'))
            rows, detected = import_kinetics_csv(exported.to_csv(index=False).encode())
            self.assertEqual(detected, basis)
            self.assertEqual(len(rows), 2)
            self.assertEqual(export_frame(rows, relative=True).columns.tolist(), EXPORT_COLUMNS)
            self.assertAlmostEqual(export_frame(rows, relative=True).iloc[0]['AP Onset (ms)'], -.5)
            self.assertAlmostEqual(rows[0]['AHP Half rise (ms)'],
                                   exported.iloc[0]['AHP Half-Fall (ms)'])
            self.assertAlmostEqual(rows[0]['AHP Amplitude from AP threshold (mV)'], -15.)

    def test_group_plots_show_p_values(self):
        records = [make_row(i, offset=float(i*10)) for i in range(6)]
        groups = {'Group 1': ['file0', 'file1', 'file2'],
                  'Group 2': ['file3', 'file4', 'file5']}
        figures, summary = compare_multiple_groups(records, groups)
        self.assertEqual(len(figures), len(COMPARISON_COLUMNS))
        self.assertIn('p=', figures[0].layout.annotations[0].text)
        self.assertIn('Holm=', figures[0].layout.annotations[0].text)
        tests = pairwise_statistics(records, groups)
        self.assertEqual(len(tests), len(COMPARISON_COLUMNS))
        self.assertTrue((tests['Holm-adjusted p-value'].dropna() >=
                         tests['Welch p-value'].dropna()).all())

    def test_missing_and_duplicate_filenames(self):
        record = make_row(0)
        frame = export_frame([record, record])
        rows, _ = import_kinetics_csv(frame.to_csv(index=False).encode())
        self.assertNotEqual(rows[0]['File ID'], rows[1]['File ID'])
        malformed = frame.drop(columns=['AHP Half-Fall (ms)'])
        with self.assertRaisesRegex(ValueError, 'Missing required'):
            import_kinetics_csv(malformed.to_csv(index=False).encode())

    def test_inadequate_n_has_unavailable_p(self):
        rows = [make_row(0), make_row(1)]
        results = pairwise_statistics(rows, {'Group 1': ['file0'], 'Group 2': ['file1']})
        self.assertTrue(results['Welch p-value'].isna().all())


if __name__ == '__main__':
    unittest.main()
