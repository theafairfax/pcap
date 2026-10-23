import io
import unittest
from pathlib import Path
from unittest.mock import patch
import numpy as np
import streamlit as st
from streamlit.testing.v1 import AppTest
from neuron_compare.bulk import KINETIC_COLUMNS
from neuron_compare.recordings import Sweep


class BulkUITests(unittest.TestCase):
    def test_batch_csv_groups_and_stale_results(self):
        st.cache_data.clear()
        uploads=[]
        # Same filename with different content must remain independently selectable.
        for data in (b'one',b'two',b'bad'):
            upload=io.BytesIO(data); upload.name='neuron.abf';uploads.append(upload)
        t=np.arange(0.,.1,.00002)
        v=np.interp(t*1000,[0,18,19,20,21,22,28,100],[-65,-65,-60,30,-65,-75,-65,-65])
        def load(data,name,channel):
            if data==b'bad':
                raise ValueError('Broken recording')
            return [Sweep(0,t,np.full_like(t,-65.)),Sweep(1,t,v)]
        def uploader(label,**kwargs):
            return uploads if label=='Bulk rheobase recordings' else None
        with patch('streamlit.file_uploader',side_effect=uploader),patch('neuron_compare.bulk.load_recording',side_effect=load):
            app=AppTest.from_file(str(Path(__file__).resolve().parents[1]/'app.py'),default_timeout=30).run()
            self.assertEqual([tab.label for tab in app.tabs],['Kinetics Visualizer','Bulk Kinetics','Compare Groups'])
            next(b for b in app.button if b.label=='Process files').click().run()
            self.assertEqual(len(app.exception),0)
            rows=app.session_state['bulk_results']['rows']
            self.assertEqual([r['Status'] for r in rows],['OK','OK','Error'])
            ids=[r['File ID'] for r in rows]
            self.assertEqual(len(set(ids)),3)
            next(w for w in app.multiselect if w.label=='Group 1 files').set_value([ids[0]]).run()
            next(w for w in app.multiselect if w.label=='Group 2 files').set_value([ids[0]]).run()
            next(b for b in app.button if b.label=='Analyze').click().run()
            self.assertTrue(any('both groups' in w.value for w in app.warning))
            next(w for w in app.multiselect if w.label=='Group 2 files').set_value([ids[1]]).run()
            next(b for b in app.button if b.label=='Analyze').click().run()
            self.assertEqual(len(app.exception),0)
            summary=app.dataframe[-1].value
            self.assertEqual(len(summary),2*len(KINETIC_COLUMNS))
            self.assertTrue((summary['n']==1).all())
            next(w for w in app.number_input if w.label=='Bulk minimum AP peak (mV)').set_value(10.).run()
            self.assertEqual(len(app.exception),0)
            self.assertFalse(any(w.label=='Group 1 files' for w in app.multiselect))
            self.assertTrue(any('Reprocess' in w.value for w in app.info))
        st.cache_data.clear()

    def test_visualizer_early_return_does_not_block_bulk_tabs(self):
        app=AppTest.from_file(str(Path(__file__).resolve().parents[1]/'app.py'),default_timeout=30).run()
        next(w for w in app.checkbox if w.label=='Try a synthetic example').uncheck().run()
        self.assertEqual(len(app.exception),0)
        self.assertTrue(any(b.label=='Process files' for b in app.button))
