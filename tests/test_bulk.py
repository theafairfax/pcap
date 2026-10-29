import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import numpy as np
import pandas as pd
from pyabf.abfWriter import writeABF1
from neuron_compare.bulk import analyze_file, compare_groups, results_frame, KINETIC_COLUMNS, COMPARISON_COLUMNS
from neuron_compare.core import Settings, first_event
from neuron_compare.recordings import Sweep


class BulkTests(unittest.TestCase):
    def sweeps(self):
        t=np.arange(0.,.1,.00002)
        v=np.interp(t*1000,[0,18,19,20,21,22,28,35,45,58,59,60,61,62,70,100],
                    [-65,-65,-60,30,-65,-75,-65,-85,-65,-65,-60,45,-65,-80,-65,-65])
        return [Sweep(0,t,np.full_like(t,-65.)), Sweep(1,t,v), Sweep(2,t,v+5)]

    def test_first_spiking_sweep_first_event_and_explicit_half_widths(self):
        sweeps=self.sweeps()
        with patch('neuron_compare.bulk.load_recording',return_value=sweeps):
            row=analyze_file(b'x','one.axgd')
        expected=first_event(sweeps[1])['measurements']
        self.assertEqual(row['Sweep'],1)
        self.assertEqual(row['APs in selected sweep'],2)
        self.assertAlmostEqual(row['AP Peak Vm (mV)'],30.)
        self.assertAlmostEqual(row['AHP Trough Vm (mV)'],-75.)
        for block,label in (('SPIKE','AP'),('AHP','AHP')):
            self.assertAlmostEqual(row[f'{label} Half width (ms)'],
                                   expected[f'{block} Half fall (ms)']-expected[f'{block} Half rise (ms)'])
        self.assertFalse(any(isinstance(v,np.ndarray) for v in row.values()))

    def test_real_generated_abf_to_csv(self):
        sweeps=self.sweeps()
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'batch.abf'
            writeABF1(np.stack([s.voltage for s in sweeps]),str(path),50000,units='mV')
            row=analyze_file(path.read_bytes(),path.name)
        self.assertEqual(row['Sweep'],1)
        self.assertAlmostEqual(row['AP Location (ms)'],20.,places=1)
        row['File ID']='a'
        csv=results_frame([row]).to_csv(index=False,na_rep='')
        restored=pd.read_csv(io.StringIO(csv))
        self.assertAlmostEqual(restored.iloc[0]['AP Half width (ms)'],row['AP Half width (ms)'])

    def test_no_ap_error_and_partial_rows(self):
        sweeps=self.sweeps()
        with patch('neuron_compare.bulk.load_recording',return_value=sweeps[:1]):
            self.assertEqual(analyze_file(b'x','silent.abf')['Status'],'No AP')
        with patch('neuron_compare.bulk.load_recording',side_effect=ValueError('Invalid voltage channel')):
            row=analyze_file(b'x','broken.abf')
            self.assertEqual(row['Status'],'Error')
            self.assertIn('Invalid voltage channel',row['Detail'])
        with patch('neuron_compare.bulk.load_recording',return_value=sweeps):
            row=analyze_file(b'x','partial.axgx',settings=Settings(end_ms=20.2))
        self.assertEqual(row['Status'],'Partial')
        self.assertEqual(row['Sweep'],1)
        self.assertTrue(np.isnan(row['AHP Trough Vm (mV)']))
        self.assertAlmostEqual(row['AP Peak Vm (mV)'],30.)

    def test_injection_window_excludes_earlier_spikes(self):
        sweeps=self.sweeps()
        with patch('neuron_compare.bulk.load_recording',return_value=sweeps):
            row=analyze_file(b'x','window.abf',settings=Settings(start_ms=50.,end_ms=90.))
        self.assertEqual(row['Sweep'],1)
        self.assertAlmostEqual(row['AP Location (ms)'],60.)
        self.assertAlmostEqual(row['AP Peak Vm (mV)'],45.)

    def test_group_validation_and_measure_specific_missing_values(self):
        with patch('neuron_compare.bulk.load_recording', return_value=self.sweeps()):
            a = analyze_file(b'file', 'a.abf')
            b = analyze_file(b'file', 'b.abf')
        a['File ID'] = 'a'
        b['File ID'] = 'b'
        b['AP Onset (ms)'] = np.nan
        figures,summary=compare_groups([a,b],['a'],['b'])
        self.assertEqual(len(figures),len(COMPARISON_COLUMNS))
        first=summary[summary['Measure']==COMPARISON_COLUMNS[0]]
        self.assertEqual(first['n'].tolist(),[1,0])
        self.assertEqual(first['Missing'].tolist(),[0,1])
        self.assertEqual(len(figures[1].data),2)
        self.assertEqual(figures[0].data[0].boxpoints,False)
        for groups in (([],['b']),(['a'],['a']),(['a'],['unknown'])):
            with self.assertRaises(ValueError):
                compare_groups([a,b],*groups)
