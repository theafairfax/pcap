"""Regression coverage for configurable slow AHP detection in bulk kinetics."""
import unittest
from unittest.mock import patch
import numpy as np
from neuron_compare.bulk import analyze_file
from neuron_compare.core import Settings, first_event
from neuron_compare.recordings import Sweep


class AdaptiveAHPTests(unittest.TestCase):
    def recording(self):
        t = np.arange(0., .080, .00002)
        # AHP trough follows the falling AP half-height by >3 ms.
        v = np.interp(t * 1000, [0, 18, 19, 20, 21, 23, 27, 32, 45, 80],
                      [-65, -65, -60, 30, -60, -68, -73, -78, -70, -65])
        return Sweep(0, t, v)

    def test_default_30_ms_trough_search_finds_slow_trough(self):
        r = first_event(self.recording())['measurements']
        self.assertEqual(Settings().ahp_trough_window_ms, 30.)
        self.assertAlmostEqual(r['AHP Location (ms)'], 32., places=1)
        self.assertAlmostEqual(r['AHP trough search end (ms)'],
                               r['SPIKE Half fall (ms)'] + 30., places=1)
        self.assertTrue(np.isfinite(r['AHP Width (ms)']))

    def test_bulk_and_visualizer_use_same_default(self):
        visualizer = first_event(self.recording())['measurements']
        with patch('neuron_compare.bulk.load_recording', return_value=[self.recording()]):
            bulk = analyze_file(b'test', 'slow_ahp.abf')
        self.assertAlmostEqual(bulk['AHP Location (ms)'], visualizer['AHP Location (ms)'])
        self.assertAlmostEqual(bulk['AHP Trough Vm (mV)'], visualizer['AHP trough Vm (mV)'])

    def test_shorter_trough_search_excludes_slow_trough(self):
        r = first_event(self.recording(), Settings(ahp_trough_window_ms=10.))['measurements']
        self.assertTrue(np.isnan(r['AHP Location (ms)']))

    def test_trough_search_larger_than_30_ms_is_rejected(self):
        with self.assertRaisesRegex(ValueError, 'at most 30 ms'):
            first_event(self.recording(), Settings(ahp_trough_window_ms=31.))

    def test_post_injection_recovery_is_optional(self):
        sw = self.recording()
        sw.current = np.where((sw.time >= .015) & (sw.time < .035), 100., 0.)
        limited = first_event(sw, Settings(ahp_trough_window_ms=15., ahp_window_ms=60.))
        extended = first_event(sw, Settings(ahp_trough_window_ms=15.,
                                            ahp_window_ms=60., ahp_post_injection=True))
        self.assertTrue(np.isnan(limited['measurements']['AHP Width (ms)']))
        self.assertTrue(np.isfinite(extended['measurements']['AHP Width (ms)']))
        self.assertGreater(extended['time_ms'][-1], 35.)

    def test_late_minimum_still_truncated_at_search_limit(self):
        t = np.arange(0., .080, .00002)
        v = np.interp(t*1000, [0,18,19,20,21,45,65,80],
                      [-65,-65,-60,30,-60,-85,-65,-65])
        r = first_event(Sweep(0,t,v))['measurements']
        self.assertTrue(np.isnan(r['AHP Location (ms)']))


if __name__ == '__main__':
    unittest.main()
