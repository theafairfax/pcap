import copy
import io
import json
import unittest
from pathlib import Path
from unittest.mock import patch
import numpy as np
from streamlit.testing.v1 import AppTest
from scripts.make_demo import demo_event
from scripts.prepare_diverse import diverse_order
from neuron_compare.supabase_library import encode_event, decode_event, catalog, fetch_event, upload_event, validate_browser_key


def allen_event(uid):
    event=demo_event(1.,12.,f'allen-{uid}')
    event['metadata'].update(source='Allen Cell Types Database',synthetic=False,specimen_id=uid,
                             species='Mus musculus',region='VISp')
    return event


class SupabaseTests(unittest.TestCase):
    def test_browser_rejects_owner_keys(self):
        validate_browser_key('sb_publishable_example')
        with self.assertRaises(ValueError):
            validate_browser_key('sb_secret_example')

    def test_lossless_codec_and_missing_values(self):
        event=allen_event(1)
        event['measurements']['AHP Width (ms)']=np.nan
        restored=decode_event(encode_event(event))
        np.testing.assert_array_equal(restored['time_ms'],event['time_ms'])
        np.testing.assert_array_equal(restored['voltage_mv'],event['voltage_mv'])
        self.assertTrue(np.isnan(restored['measurements']['AHP Width (ms)']))
        self.assertEqual(restored['metadata']['id'],'allen-1')

    def test_upload_compact_object_then_catalog(self):
        with patch('neuron_compare.supabase_library.request',return_value=b'') as req:
            size=upload_event('https://example.supabase.co','private',allen_event(2))
        self.assertGreater(size,0)
        self.assertEqual(req.call_count,2)
        row=json.loads(req.call_args_list[1].kwargs['data'])
        self.assertEqual(row['species'],'Mus musculus')
        self.assertNotIn('time_ms',row)
        self.assertIn('AHP|Event onset|False',row['plot_bounds'])
        self.assertTrue(row['storage_path'].endswith('.npz'))
        with self.assertRaises(ValueError):
            upload_event('https://example.supabase.co','private',demo_event())

    def test_catalog_pages_and_selected_identity(self):
        rows=[{'id':str(i)} for i in range(500)]
        with patch('neuron_compare.supabase_library.request',side_effect=[json.dumps(rows).encode(),b'[{"id":"last"}]']) as req:
            result=catalog('https://example.supabase.co','public')
        self.assertEqual(len(result),501)
        self.assertIn('offset=500',req.call_args_list[1].args[2])
        event=allen_event(3)
        with patch('neuron_compare.supabase_library.request',return_value=encode_event(event)) as req:
            restored=fetch_event('https://example.supabase.co','public',{'id':'allen-3','storage_path':'v1/3.npz'})
        self.assertEqual(restored['metadata']['id'],'allen-3')
        self.assertEqual(req.call_count,1)

    def test_diverse_order_alternates_species_and_groups(self):
        cells=[dict(id=i,species=species,structure_area_abbrev=region) for i,(species,region) in enumerate([
            ('mouse','VISp'),('mouse','VISp'),('mouse','SSp'),('human','MTG'),('human','MTG'),('human','Other')])]
        ordered=list(diverse_order(cells))
        self.assertNotEqual(ordered[0]['species'],ordered[1]['species'])
        self.assertNotEqual(ordered[0]['structure_area_abbrev'],ordered[2]['structure_area_abbrev'])
        self.assertEqual(len({c['id'] for c in ordered}),len(cells))
        self.assertEqual([c['id'] for c in ordered],[c['id'] for c in diverse_order(cells)])

    def test_app_fetches_only_selected_waveforms(self):
        import streamlit as st
        st.cache_data.clear()
        events=[allen_event(5),allen_event(6)]
        rows=[]
        for event in events:
            with patch('neuron_compare.supabase_library.request',return_value=b'') as req:
                upload_event('https://example.supabase.co','private',event)
            rows.append(json.loads(req.call_args_list[1].kwargs['data']))
        by_id={e['metadata']['id']:e for e in events}
        config={'supabase':{'url':'https://example.supabase.co','publishable_key':'sb_publishable_test'}}
        with patch('streamlit.secrets',config), \
             patch('neuron_compare.supabase_library.catalog',return_value=rows), \
             patch('neuron_compare.supabase_library.fetch_event',side_effect=lambda url,key,row:copy.deepcopy(by_id[row['id']])) as fetch:
            app=AppTest.from_file(str(Path(__file__).resolve().parents[1]/'app.py'),default_timeout=30).run()
            self.assertEqual(len(app.exception),0)
            self.assertEqual(fetch.call_count,0)
            next(w for w in app.selectbox if w.label=='Collection').set_value('Supabase library').run()
            self.assertEqual(len(app.exception),0)
            self.assertEqual(fetch.call_count,1)
            next(w for w in app.button if w.label=='Next →').click().run()
            self.assertEqual(len(app.exception),0)
            self.assertEqual(fetch.call_count,2)
        st.cache_data.clear()
