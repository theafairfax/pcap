import tempfile
import unittest
from pathlib import Path
import numpy as np
from scripts.make_demo import demo_event
from neuron_compare.core import Settings, first_event, metrics, alignment, injection_window, count_spikes, coordinates
from neuron_compare.recordings import Sweep
from neuron_compare.references import save_collection, load_collection


class CoreTests(unittest.TestCase):
    def train(self):
        t=np.arange(0.,.1,.00002)
        v=np.interp(t*1000,[0,18,19,20,21,22.5,40,58,59,60,61,62.5,80,100],
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
        self.assertAlmostEqual(metrics(event,'AHP')['AP peak to trough (ms)'],2.5)
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

    def test_both_views_use_ap_landmark_window(self):
        event=first_event(self.train())
        r=event['measurements']
        for block in ('SPIKE','AHP'):
            for mode in ('Event location','Event onset'):
                for normalize in (False,True):
                    x,y,origin,base,scale=coordinates(event,block,mode,normalize)
                    self.assertAlmostEqual(x[0]+origin,r['SPIKE Onset (ms)']-2.)
                    if block == 'SPIKE':
                        self.assertAlmostEqual(x[-1]+origin,r['SPIKE Half fall (ms)']+3.)
                    else:
                        self.assertGreaterEqual(x[-1]+origin,r['AHP Location (ms)']+3.)
                    self.assertAlmostEqual(y[-1],(np.interp(x[-1]+origin,event['time_ms'],event['voltage_mv'])-base)/scale)
        # Cropping the display does not discard stored recovery samples.
        self.assertGreater(event['time_ms'][-1],r['SPIKE Half fall (ms)']+3.)

    def test_display_clips_to_capture_and_requires_landmarks(self):
        event=first_event(self.train())
        keep=(event['time_ms']>=18.5)&(event['time_ms']<=22.)
        event['time_ms']=event['time_ms'][keep]
        event['voltage_mv']=event['voltage_mv'][keep]
        x,y,origin,*_=coordinates(event,'SPIKE','Event location',False)
        self.assertAlmostEqual(x[0]+origin,event['time_ms'][0])
        self.assertAlmostEqual(x[-1]+origin,event['time_ms'][-1])
        event['measurements']['SPIKE Half fall (ms)']=np.nan
        with self.assertRaises(ValueError):
            coordinates(event,'SPIKE','Event location',False)

    def test_ahp_trough_uses_half_fall_cutoff_but_retains_recovery(self):
        t=np.arange(0.,.1,.00002)
        # A fast AHP at 22 ms followed by a deeper, unrelated dip at 35 ms.
        v=np.interp(t*1000,[0,18,19,20,21,22,28,35,45,100],
                    [-65,-65,-60,30,-65,-75,-65,-85,-65,-65])
        event=first_event(Sweep(0,t,v))
        r=event['measurements']
        self.assertAlmostEqual(r['AHP Location (ms)'],22.)
        self.assertAlmostEqual(r['AHP trough search end (ms)'],r['SPIKE Half fall (ms)']+3.)
        self.assertLessEqual(r['AHP Location (ms)'],r['SPIKE Half fall (ms)']+3.)
        # Recovery measurements and stored capture can extend past the trough-search cutoff.
        self.assertGreater(r['AHP Half fall (ms)'],r['AHP trough search end (ms)'])
        self.assertGreater(event['time_ms'][-1],35.)
        # With only a late trough, report unresolved instead of selecting it.
        v=np.interp(t*1000,[0,18,19,20,21,35,45,100],
                    [-65,-65,-60,30,-65,-85,-65,-65])
        r=first_event(Sweep(0,t,v))['measurements']
        self.assertTrue(np.isnan(r['AHP Location (ms)']))

    def test_legacy_reference_is_remeasured_with_new_ahp_rule(self):
        from neuron_compare.core import ANALYSIS_VERSION, LEGACY_ANALYSIS_VERSION
        event=demo_event()
        event['analysis_version']=LEGACY_ANALYSIS_VERSION
        event['measurements']['AHP Location (ms)']=39.
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'legacy.json'
            save_collection(path,[event])
            restored=load_collection(path)[0]
        self.assertEqual(restored['analysis_version'],ANALYSIS_VERSION)
        self.assertAlmostEqual(restored['measurements']['AHP Location (ms)'],22.5)
        np.testing.assert_array_equal(restored['time_ms'],event['time_ms'])

    def test_missing_half_fall_and_early_injection_end_do_not_find_late_ahp(self):
        for end_ms in (20.2,21.8):
            event=first_event(self.train(),Settings(end_ms=end_ms))
            self.assertTrue(np.isnan(event['measurements']['AHP Location (ms)']))
        r=first_event(self.train(),Settings(end_ms=20.2))['measurements']
        self.assertIn('No AP half-fall',r['Status'])
