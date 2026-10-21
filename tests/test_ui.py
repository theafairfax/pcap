import unittest
import io
import tempfile
from unittest.mock import patch
import numpy as np
from pyabf.abfWriter import writeABF1
from pathlib import Path
from streamlit.testing.v1 import AppTest
from neuron_compare.plotting import overlay
from scripts.make_demo import demo_event


class UITests(unittest.TestCase):
    def test_browsing_and_ahp_view(self):
        app=AppTest.from_file(str(Path(__file__).resolve().parents[1]/'app.py'),default_timeout=30).run()
        self.assertEqual(len(app.exception),0)
        original=app.session_state['reference_index']
        next(b for b in app.button if b.label=='Next →').click().run()
        self.assertEqual(len(app.exception),0)
        self.assertEqual(app.session_state['reference_index'],original+1)
        next(r for r in app.radio if r.label=='Waveform').set_value('AHP').run()
        self.assertEqual(len(app.exception),0)
        self.assertIn('AP peak to trough (ms)',app.dataframe[0].value['Dynamic'].tolist())
        next(b for b in app.button if b.label=='← Previous').click().run()
        self.assertEqual(app.session_state['reference_index'],original)

    def test_fixed_axes_and_trace_order(self):
        query=demo_event(.9,10,'q');a=demo_event(.6,8,'a');b=demo_event(1.4,18,'b')
        first=overlay(query,a,[a,b]);second=overlay(query,b,[a,b])
        self.assertEqual(first.layout.xaxis.range,second.layout.xaxis.range)
        self.assertEqual(first.layout.yaxis.range,second.layout.yaxis.range)
        self.assertEqual(first.data[0].name,'Reference')
        for block in ('SPIKE','AHP'):
            fig=overlay(query,a,[a,b],block,'Event location',True)
            self.assertGreater(len(fig.data),0)

    def test_uploaded_abf_defaults_to_first_spiking_sweep(self):
        t=np.arange(20000)/20000.
        base=np.where(t<.1,0.,-65.)
        spike=np.interp(t*1000,[0,100,198,199,200,201,204,220,598,599,600,601,604,620,1000],
                        [0,-65,-65,-60,30,-65,-77,-65,-65,-60,35,-65,-77,-65,-65])
        spike[t<.1]=0.
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'upload.abf'
            writeABF1(np.stack([base,spike]),str(p),20000,units='mV')
            upload=io.BytesIO(p.read_bytes());upload.name='upload.abf'
            with patch('streamlit.file_uploader',return_value=upload):
                app=AppTest.from_file(str(Path(__file__).resolve().parents[1]/'app.py'),default_timeout=30).run()
        self.assertEqual(len(app.exception),0)
        sweep=next(w for w in app.selectbox if w.label=='Sweep')
        self.assertEqual(sweep.value,1)
        self.assertTrue(all('Synthetic example' in w.value for w in app.warning), [w.value for w in app.warning])
        marker_table=app.dataframe[1].value
        location=marker_table[(marker_table['Neuron']=='Your neuron')&(marker_table['Marker']=='Location')]
        self.assertAlmostEqual(location.iloc[0]['Sweep time (ms)'],200.,places=1)
