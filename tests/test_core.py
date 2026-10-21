import tempfile
import unittest
from pathlib import Path
import numpy as np
from scripts.make_demo import demo_event
from neuron_compare.core import Settings, first_event, metrics, alignment, injection_window, count_spikes
from neuron_compare.recordings import Sweep
from neuron_compare.references import save_collection, load_collection


class CoreTests(unittest.TestCase):
    def train(self):
        t=np.arange(0.,.1,.00002)
        v=np.interp(t*1000,[0,18,19,20,21,24,40,58,59,60,61,64,80,100],
                    [-65,-65,-60,30,-65,-77,-65,-65,-60,35,-65,-80,-65,-65])
        return Sweep(0,t,v)

    def test_first_ap_only_in_selected_sweep(self):
        sw=self.train()
        self.assertEqual(count_spikes(sw,Settings()),2)
        event=first_event(sw)
        self.assertAlmostEqual(event['measurements']['SPIKE Location (ms)'],20.)
        second=first_event(sw,Settings(start_ms=50.,end_ms=90.))
        self.assertAlmostEqual(second['measurements']['SPIKE Location (ms)'],60.)
        self.assertLess(event['time_ms'][-1],60.)

    def test_fractional_crossings_and_relative_origin(self):
        event=demo_event()
        r=event['measurements']
        for block in ('SPIKE','AHP'):
            self.assertAlmostEqual(r[f'{block} Rise (ms)'],r[f'{block} Rise 90% (ms)']-r[f'{block} Rise 10% (ms)'])
            self.assertEqual(r[f'{block} Location relative (ms)'],0.)
            self.assertGreater(r[f'{block} Width (ms)'],0.)
        self.assertAlmostEqual(metrics(event,'AHP')['AP peak to trough (ms)'],4.)
        self.assertEqual(alignment(event,'AHP','AP peak'),20.)

    def test_window_and_no_spike(self):
        sw=self.train()
        sw.current=np.where((sw.time>=.05)&(sw.time<.09),100.,0.)
        lo,hi,source=injection_window(sw,Settings())
        self.assertAlmostEqual(lo,.05)
        self.assertEqual(count_spikes(sw,Settings()),1)
        self.assertAlmostEqual(first_event(sw)['measurements']['SPIKE Location (ms)'],60.)
        with self.assertRaises(ValueError):
            first_event(sw,Settings(start_ms=0.,end_ms=10.))
        with self.assertRaises(ValueError):
            injection_window(sw,Settings(start_ms=100.,end_ms=10.))

    def test_unresolved_ahp_is_missing_and_json_is_strict(self):
        sw=self.train()
        e=first_event(sw,Settings(end_ms=21.))
        self.assertTrue(np.isnan(e['measurements']['AHP Location (ms)']))
        e['metadata']['id']='missing'
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'references.json'
            save_collection(p,[e])
            self.assertNotIn('NaN',p.read_text())
            restored=load_collection(p)[0]
            self.assertTrue(np.isnan(restored['measurements']['AHP Location (ms)']))
            np.testing.assert_allclose(restored['voltage_mv'],e['voltage_mv'])
