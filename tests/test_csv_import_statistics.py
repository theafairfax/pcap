"""Saved bulk CSV import and statistical comparison regression tests."""
import unittest
import numpy as np
from neuron_compare.bulk import (
    COLUMNS, export_frame, import_kinetics_csv, compare_multiple_groups,
    pairwise_statistics, COMPARISON_COLUMNS, EXPORT_COLUMNS, significance_label, _bh_adjust,
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
        'AP Peak Vm (mV)': 30. + index,
        'AHP Trough Vm (mV)': -75. - index,
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
            self.assertAlmostEqual(rows[0]['AP Peak Vm (mV)'], 30.)
            self.assertAlmostEqual(rows[0]['AHP Trough Vm (mV)'], -75.)

    def test_legacy_csv_without_voltage_fields_is_still_importable(self):
        from neuron_compare.bulk import LEGACY_EXPORT_COLUMNS
        previous = export_frame([make_row(0), make_row(1)])[LEGACY_EXPORT_COLUMNS]
        loaded, _ = import_kinetics_csv(previous.to_csv(index=False).encode())
        self.assertEqual(loaded[0]['Status'], 'OK')
        self.assertTrue(np.isnan(loaded[0]['AP Peak Vm (mV)']))
        self.assertTrue(np.isnan(loaded[0]['AHP Trough Vm (mV)']))
        plotted, _ = compare_multiple_groups(loaded, {'A': [loaded[0]['File ID']], 'B': [loaded[1]['File ID']]})
        self.assertEqual(len(plotted), len(COMPARISON_COLUMNS))
        self.assertEqual(len(plotted[COMPARISON_COLUMNS.index('AP peak Vm (mV)')].data[0].y), 0)

    def test_group_plots_show_p_values(self):
        records = [make_row(i, offset=float(i*10)) for i in range(6)]
        groups = {'Group 1': ['file0', 'file1', 'file2'],
                  'Group 2': ['file3', 'file4', 'file5']}
        figures, summary = compare_multiple_groups(records, groups)
        self.assertEqual(len(figures), len(COMPARISON_COLUMNS))
        self.assertIn('Welch p=', figures[0].layout.annotations[0].text)
        self.assertIn('BH FDR p=', figures[0].layout.annotations[0].text)
        self.assertIn('Holm p=', figures[0].layout.annotations[0].text)
        tests = pairwise_statistics(records, groups)
        self.assertEqual(len(tests), len(COMPARISON_COLUMNS))
        self.assertTrue((tests['Holm-adjusted p-value'].dropna() >=
                         tests['Welch p-value'].dropna()).all())

    def test_bh_stepup_and_invalid_pvalues(self):
        p = _bh_adjust([.04, .001, np.nan, .02, .008, .12])
        np.testing.assert_allclose(
            [p[i] for i in (0, 1, 3, 4, 5)],
            [.05, .005, 1/30, .02, .12],
            rtol=1e-10,
        )
        self.assertTrue(np.isnan(p[2]))

    def test_method_controls_brackets_not_numeric_results(self):
        records = [make_row(i) for i in range(6)]
        for i, record in enumerate(records):
            record['AP Half width (ms)'] = .1 * (i % 3) + (1. if i >= 3 else 0.)
        groups = {'Control': ['file0', 'file1', 'file2'],
                  'Drug': ['file3', 'file4', 'file5']}
        test = pairwise_statistics(records, groups)
        self.assertIn('BH-adjusted p-value', test.columns)
        values = []
        for method, column in (
            ("Welch's t-test (uncorrected)", 'Welch p-value'),
            ('Benjamini-Hochberg (FDR)', 'BH-adjusted p-value'),
            ('Holm-Bonferroni', 'Holm-adjusted p-value'),
        ):
            figures, _ = compare_multiple_groups(records, groups, significance_method=method)
            fig = next(f for f in figures if f.layout.yaxis.title.text == 'AP Half width (ms)')
            self.assertIn('Welch p=', fig.layout.annotations[0].text)
            self.assertIn('BH FDR p=', fig.layout.annotations[0].text)
            self.assertIn('Holm p=', fig.layout.annotations[0].text)
            relevant = test.loc[test['Measure'].eq('AP Half width (ms)')].iloc[0]
            self.assertEqual(fig.layout.annotations[1].text, significance_label(relevant[column]))
            values.append(fig.layout.annotations[0].text)
        self.assertEqual(len(set(values)), 1)
        with self.assertRaisesRegex(ValueError, 'Unknown significance'):
            compare_multiple_groups(records, groups, significance_method='invalid')

    def test_significance_thresholds_and_brackets(self):
        self.assertEqual(significance_label(.05), 'n.s.')
        self.assertEqual(significance_label(.0499), '*')
        self.assertEqual(significance_label(.0099), '**')
        self.assertEqual(significance_label(.0009), '***')
        self.assertEqual(significance_label(np.nan), 'N/A')
        records = [make_row(i) for i in range(9)]
        for i, record in enumerate(records):
            record['AP Half width (ms)'] = float(i) / 5
        groups = {f'Group {i+1}': [f'file{3*i+j}' for j in range(3)] for i in range(3)}
        figures, _ = compare_multiple_groups(records, groups)
        fig = next(f for f in figures if f.layout.yaxis.title.text == 'AP Half width (ms)')
        self.assertTrue(all(trace.boxpoints == 'all' for trace in fig.data))
        self.assertEqual(len(fig.layout.shapes), 3)
        self.assertEqual(len([a for a in fig.layout.annotations if a.yref == 'y']), 3)
        self.assertGreater(fig.layout.yaxis.range[1], max(r['AP Half width (ms)'] for r in records))

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
