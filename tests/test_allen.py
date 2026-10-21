import unittest
from types import SimpleNamespace
import numpy as np
from neuron_compare.core import Settings
from scripts.prepare_allen import prepare_cell, filter_catalog, main


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

    def test_catalog_filter_and_metadata_only_listing(self):
        from unittest.mock import patch
        import io
        import sys
        cells=[dict(id=1,species='Homo sapiens',structure_area_abbrev='MTG'),
               dict(id=2,species='Mus musculus',structure_area_abbrev='VISp')]
        self.assertEqual(filter_catalog(cells,['mtg']),[cells[0]])
        cache=unittest.mock.Mock()
        cache.get_cells.return_value=[cells[0]]
        factory=unittest.mock.Mock(return_value=cache)
        module=SimpleNamespace(CellTypesCache=factory)
        with patch.dict(sys.modules,{'allensdk.core.cell_types_cache':module}), \
             patch.object(sys,'argv',['prepare_allen.py','--species','human','--regions','MTG','--list-cells']), \
             patch('sys.stdout',new_callable=io.StringIO) as output:
            main()
        cache.get_cells.assert_called_once_with(species=['Homo sapiens'])
        cache.get_ephys_data.assert_not_called()
        self.assertIn('Homo sapiens',output.getvalue())
