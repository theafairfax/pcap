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
        self.assertEqual(app.title[0].value,'Patch Clamp Analysis Platform')
        next(w for w in app.selectbox if w.label=='Collection').set_value(next(p for p in (Path(__file__).resolve().parents[1]/'references').glob('*.json') if p.stem=='demo')).run()
        original=app.session_state['reference_index']
        next(b for b in app.button if b.label=='Next →').click().run()
        self.assertEqual(len(app.exception),0)
        self.assertEqual(app.session_state['reference_index'],original+1)
        next(r for r in app.radio if r.label=='Waveform').set_value('AHP').run()
        self.assertEqual(len(app.exception),0)
        self.assertIn('AP peak to trough (ms)',app.dataframe[0].value['Dynamic'].tolist())
        next(r for r in app.radio if r.label=='Align traces at').set_value('Onset').run()
        self.assertEqual(len(app.exception),0)
        self.assertIn('Species',[w.label for w in app.selectbox])
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

    def test_uploaded_reference_sweep_and_collection_switch(self):
        from neuron_compare.recordings import Sweep
        import streamlit as st
        st.cache_data.clear()
        t=np.arange(20000)/20000.
        def sweep(index,peak):
            v=np.interp(t*1000,[0,100,198,199,200,201,204,220,1000],
                        [-65,-65,-65,-60,peak,-65,-77,-65,-65])
            return Sweep(index,t,v)
        sweeps=[Sweep(0,t,np.full_like(t,-65.)),sweep(1,30),sweep(2,45)]
        primary=io.BytesIO(b'primary');primary.name='primary.abf'
        reference=io.BytesIO(b'reference');reference.name='reference.axgd'
        def uploader(label,**kwargs):
            return reference if label=='Reference rheobase recording' else primary
        with patch('streamlit.file_uploader',side_effect=uploader), patch('neuron_compare.recordings.load_recording',return_value=sweeps):
            app=AppTest.from_file(str(Path(__file__).resolve().parents[1]/'app.py'),default_timeout=30).run()
            next(w for w in app.selectbox if w.label=='Collection').set_value('User Uploaded').run()
            self.assertEqual(len(app.exception),0)
            self.assertEqual(next(w for w in app.selectbox if w.label=='Reference sweep').value,1)
            self.assertFalse(any(w.label=='Species' for w in app.selectbox))
            next(w for w in app.selectbox if w.label=='Reference sweep').set_value(2).run()
            self.assertEqual(len(app.exception),0)
            table=app.dataframe[0].value.set_index('Dynamic')
            self.assertAlmostEqual(table.loc['Peak Vm (mV)','Reference'],45.)
            self.assertAlmostEqual(table.loc['Peak Vm (mV)','Your neuron'],30.)
            next(w for w in app.radio if w.label=='Waveform').set_value('AHP').run()
            self.assertEqual(len(app.exception),0)
            self.assertIn('AP peak to trough (ms)',app.dataframe[0].value['Dynamic'].tolist())
            next(w for w in app.selectbox if w.label=='Collection').set_value(next(p for p in (Path(__file__).resolve().parents[1]/'references').glob('*.json') if p.stem=='demo')).run()
            self.assertEqual(len(app.exception),0)
            self.assertTrue(any(w.label=='Species' for w in app.selectbox))
        st.cache_data.clear()

    def test_both_alignment_markers_land_at_zero_on_centered_axes(self):
        query=demo_event(.9,10,'q');ref=demo_event(1.4,18,'r')
        for block in ('SPIKE','AHP'):
            for mode,marker in [('Event location','Location'),('Event onset','Onset')]:
                fig=overlay(query,ref,[ref],block,mode)
                left,right=fig.layout.xaxis.range
                self.assertAlmostEqual(left,-right)
                points=[trace for trace in fig.data if trace.name.endswith(' · '+marker)]
                self.assertEqual(len(points),2)
                for point in points:
                    self.assertAlmostEqual(point.x[0],0.)

    def test_species_filter_resets_stale_region_and_reference(self):
        human=demo_event(1,12,'human');mouse=demo_event(.8,10,'mouse')
        human['metadata'].update(species='Homo sapiens',region='MTG')
        mouse['metadata'].update(species='Mus musculus',region='VISp')
        import streamlit as st
        st.cache_data.clear()
        with patch('neuron_compare.references.load_collection',return_value=[human,mouse]):
            app=AppTest.from_file(str(Path(__file__).resolve().parents[1]/'app.py'),default_timeout=30).run()
            next(w for w in app.selectbox if w.label=='Region').set_value('MTG').run()
            next(w for w in app.selectbox if w.label=='Species').set_value('Mus musculus').run()
            self.assertEqual(len(app.exception),0)
            self.assertEqual(next(w for w in app.selectbox if w.label=='Region').value,'All')
            self.assertEqual(next(w for w in app.selectbox if w.label=='Reference neuron').options,[mouse['metadata']['label']])

    def test_legacy_cloud_bounds_do_not_clip_reference_tail(self):
        query=demo_event(.9,8,'q');ref=demo_event(1.2,25,'r')
        keep=query['time_ms']<=query['measurements']['SPIKE Location (ms)']+2
        query['time_ms']=query['time_ms'][keep]
        query['voltage_mv']=query['voltage_mv'][keep]
        for mode in ('Event location','Event onset'):
            for normalize in (False,True):
                fig=overlay(query,ref,[],mode=mode,normalize=normalize,range_bounds=[[-5,1,-65,30]])
                lo,hi=fig.layout.xaxis.range
                ymin,ymax=fig.layout.yaxis.range
                self.assertAlmostEqual(lo,-hi)
                for line in [trace for trace in fig.data if trace.mode=='lines']:
                    self.assertGreaterEqual(hi,max(line.x))
                    self.assertLessEqual(lo,min(line.x))
                    self.assertLessEqual(ymin,min(line.y))
                    self.assertGreaterEqual(ymax,max(line.y))
                reference=next(trace for trace in fig.data if trace.name=='Reference')
                self.assertGreater(reference.x[-1],30.)
