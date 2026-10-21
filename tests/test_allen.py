import unittest
from types import SimpleNamespace
import numpy as np
from neuron_compare.core import Settings
from scripts.prepare_allen import prepare_cell


class AllenTests(unittest.TestCase):
    def test_lowest_spiking_step_and_first_ap(self):
        t=np.arange(0.,.12,.00002)
        def sweep(number):
            v=np.interp(t*1000,[0,28,29,30,31,34,50,58,59,60,61,64,80,120],
                        [-65,-65,-60,30,-65,-77,-65,-65,-60,35,-65,-77,-65,-65])
            current=np.where((t>=.02)&(t<.1),{1:150,2:100,3:50}[number],0.)
            if number==3:
                v[:]=-65
            return dict(response=v/1000,stimulus=current*1e-12,sampling_rate=50000,index_range=[0,len(t)-1])
        cache=SimpleNamespace(get_ephys_sweeps=lambda _: [dict(stimulus_name='Long Square',sweep_number=i) for i in (1,2,3)],
                              get_ephys_data=lambda _:SimpleNamespace(get_sweep=sweep))
        event=prepare_cell(cache,dict(id=123,structure_area_abbrev='VISp',transgenic_line='Sst-example'),Settings())
        self.assertEqual(event['metadata']['source_sweep'],2)
        self.assertEqual(event['metadata']['injected_current_pa'],100.)
        self.assertAlmostEqual(event['measurements']['SPIKE Location (ms)'],30.)
        self.assertFalse(event['metadata']['synthetic'])
