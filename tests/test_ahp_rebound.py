"""AHP landmark and rebound regression checks."""
import unittest
import numpy as np
from neuron_compare.core import Settings, first_event, metrics
from neuron_compare.recordings import Sweep


class ReboundLandmarkTests(unittest.TestCase):
    def recording(self, rebound=True):
        t = np.arange(0., .080, .00002)
        times = [0, 18, 19, 20, 21, 22.5, 28, 34, 40, 80]
        volts = [-65, -65, -60, 30, -65, -77, -65,
                 -60 if rebound else -65,
                 -65, -65]
        return Sweep(0, t, np.interp(t*1000, times, volts))

    def test_explicit_landmarks_and_rebound(self):
        event = first_event(self.recording())
        r = event['measurements']
        self.assertAlmostEqual(r['AHP Location (ms)'], 22.5, places=1)
        self.assertAlmostEqual(r['AHP trough Vm (mV)'], -77., places=1)
        self.assertGreater(r['AHP Onset (ms)'], r['SPIKE Location (ms)'])
        self.assertGreater(r['AHP Half fall (ms)'], r['AHP Location (ms)'])
        self.assertAlmostEqual(r['AHP Rebound (ms)'], 34., places=1)
        self.assertAlmostEqual(r['AHP Rebound latency (ms)'], 11.5, places=1)
        values = metrics(event, 'AHP')
        self.assertAlmostEqual(values['AHP rebound latency from trough (ms)'], 11.5, places=1)

    def test_no_rebound_does_not_invent_peak(self):
        r = first_event(self.recording(rebound=False))['measurements']
        self.assertTrue(np.isnan(r['AHP Rebound (ms)']))
        self.assertTrue(np.isnan(r['AHP Rebound latency (ms)']))


if __name__ == '__main__':
    unittest.main()
