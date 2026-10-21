import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import numpy as np
from pyabf.abfWriter import writeABF1
import neo
import quantities as pq
from neuron_compare.recordings import load_recording


class ReaderTests(unittest.TestCase):
    def test_generated_abf_scaling(self):
        v=np.zeros((2,10000));v[:,9000:9004]=[[-70,-60,-50,-40],[10,20,30,40]]
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'fixture.abf';writeABF1(v,str(p),10000,units='mV')
            sw=load_recording(p.read_bytes(),p.name)
        self.assertEqual(len(sw),2)
        np.testing.assert_allclose(sw[1].voltage,v[1],atol=.01)
        self.assertEqual(sw[1].time[0],0.)
        self.assertAlmostEqual(sw[0].time[1],.0001)

    def test_axograph_units_channels_and_temp_cleanup(self):
        v=neo.AnalogSignal(np.array([-.065,-.060,.030,-.070])[:,None],units=pq.V,sampling_rate=10000*pq.Hz)
        c=neo.AnalogSignal(np.array([0.,.1,.1,0.])[:,None],units=pq.nA,sampling_rate=10000*pq.Hz)
        block=SimpleNamespace(segments=[SimpleNamespace(analogsignals=[c,v])])
        paths=[]
        def reader(path):
            paths.append(path);return SimpleNamespace(read_block=lambda:block)
        with patch('neo.io.AxographIO',side_effect=reader):
            sweeps=load_recording(b'fixture','fixture.axgd')
        np.testing.assert_allclose(sweeps[0].voltage,[-65,-60,30,-70])
        np.testing.assert_allclose(sweeps[0].current,[0,100,100,0])
        self.assertFalse(Path(paths[0]).exists())
        block.segments[0].analogsignals=[c]
        with patch('neo.io.AxographIO',return_value=SimpleNamespace(read_block=lambda:block)):
            with self.assertRaisesRegex(ValueError,'voltage channels'):
                load_recording(b'fixture','recording.axgx')
