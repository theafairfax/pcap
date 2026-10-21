"""Run with: streamlit run app.py"""
import hashlib
from pathlib import Path
import numpy as np
import pandas as pd
import streamlit as st
from neuron_compare.recordings import load_recording
from neuron_compare.core import Settings, count_spikes, first_event, metrics, MARKERS
from neuron_compare.references import load_collection
from neuron_compare.plotting import overlay

ROOT=Path(__file__).resolve().parent
st.set_page_config(page_title='Patch Clamp Analysis Platform',page_icon='〰️',layout='wide')
st.title('Patch Clamp Analysis Platform')
st.caption('One neuron. One first spike. Explore the differences.')


@st.cache_data(max_entries=2,show_spinner='Reading recording…')
def read_recording(data,name,channel):
    return load_recording(data,name,channel)


@st.cache_data(max_entries=16,show_spinner=False)
def analyze(sweep,settings):
    return first_event(sweep,settings)


@st.cache_data(max_entries=4,show_spinner=False)
def read_references(path,mtime):
    return load_collection(path)


def step_reference(delta,total):
    st.session_state['reference_index']=(st.session_state.get('reference_index',0)+delta)%total


with st.sidebar:
    st.header('Your neuron')
    upload=st.file_uploader('Rheobase recording',type=['abf','axgd','axgx'],accept_multiple_files=False)
    demo=st.checkbox('Try a synthetic example',value=upload is None)
    with st.expander('Adjust analysis'):
        st.caption('Current-clamp step protocols only. Verify the highlighted injection window against the trace.')
        channel=st.number_input('Voltage channel rank (0-based)',0,32,0,help='Rank among voltage channels, not the ADC channel number.')
        height=st.number_input('Minimum AP peak (mV)',value=-10.)
        prominence=st.number_input('Minimum prominence (mV)',min_value=0.,value=20.)
        dvdt=st.number_input('Onset dV/dt (mV/ms)',min_value=.1,value=20.)
        ahp_window=st.number_input('AHP search after AP peak (ms)',min_value=1.,value=50.)
        custom=st.checkbox('Set injection window manually')
        start=st.number_input('Injection start (ms)',min_value=0.,value=100.,disabled=not custom)
        end=st.number_input('Injection end (ms)',min_value=0.,value=600.,disabled=not custom)
        normalize=st.checkbox('Normalize amplitude',help='Threshold becomes zero; the event magnitude becomes one. Time is never stretched.')
        highlight=st.selectbox('Highlight dynamic',['All markers']+list(MARKERS))
    settings=Settings(height=height,prominence=prominence,dvdt_threshold=dvdt,ahp_window_ms=ahp_window,
                      start_ms=start if custom else None,end_ms=end if custom else None)

paths=sorted((ROOT/'references').glob('*.json'))
if not paths:
    st.error('No reference collections found. Run python scripts/make_demo.py or prepare an Allen collection.'); st.stop()
try:
    with st.sidebar:
        st.header('Reference collection')
        path=st.selectbox('Collection',paths,format_func=lambda p:p.stem)
    references=read_references(str(path),path.stat().st_mtime_ns)
except Exception as err:
    st.error(f'Could not read reference collection: {err}'); st.stop()
if not references:
    st.info('This reference collection is empty. Prepare at least one qualifying cell.'); st.stop()

query=None
if upload is not None:
    try:
        sweeps=read_recording(upload.getvalue(),upload.name,int(channel))
        counts=[count_spikes(s,settings) for s in sweeps]
        default=next((i for i,n in enumerate(counts) if n),0)
        identity=hashlib.sha256(upload.getvalue()).hexdigest()[:12]
        selected=st.sidebar.selectbox('Sweep',range(len(sweeps)),index=default,
                    format_func=lambda i:f'Sweep {sweeps[i].index} · {counts[i]} APs',key='sweep_'+identity)
        sw=sweeps[selected]
        query=analyze(sw,settings)
        query['metadata'].update(label=upload.name,source='Your upload',id=identity)
        with st.expander('Check source sweep'):
            import plotly.graph_objects as go
            fig=go.Figure(go.Scatter(x=sw.time[::max(1,len(sw.time)//20000)]*1000,
                                    y=sw.voltage[::max(1,len(sw.time)//20000)],line=dict(color='#111827')))
            meta=query['metadata']
            fig.add_vrect(x0=meta['injection_start_ms'],x1=meta['injection_end_ms'],fillcolor='#14b8a6',opacity=.12,line_width=0)
            fig.update_layout(xaxis_title='Sweep time (ms)',yaxis_title='Vm (mV)',height=280)
            st.plotly_chart(fig,width='stretch')
            st.caption(meta['window_source']+'. Analysis uses only the first AP during this window. AHP searches stop at the next AP onset, window end, or configured limit.')
    except Exception as err:
        st.warning(str(err)); st.stop()
elif demo:
    from scripts.make_demo import demo_event
    query=demo_event(.9,10,'Your synthetic example')
    st.info('Synthetic demonstration: these waveforms have no biological cell-type labels.')
else:
    st.info('Upload one ABF or AXGD/AXGX rheobase recording to begin.'); st.stop()

left,right=st.columns([3,1],gap='large')
with right:
    st.subheader('Browse neurons')
    species=st.selectbox('Species',['All']+sorted({str(r['metadata'].get('species') or 'Unknown') for r in references}))
    species_pool=[r for r in references if species=='All' or str(r['metadata'].get('species') or 'Unknown')==species]
    regions=['All']+sorted({str(r['metadata'].get('region') or 'Unknown') for r in species_pool})
    if st.session_state.get('reference_region','All') not in regions:
        st.session_state['reference_region']='All'
    region=st.selectbox('Region',regions,key='reference_region')
    pool=[r for r in species_pool if region=='All' or str(r['metadata'].get('region') or 'Unknown')==region]
    pool_key=(str(path),species,region)
    if st.session_state.get('pool_key')!=pool_key:
        st.session_state['pool_key']=pool_key; st.session_state['reference_index']=0
    st.session_state['reference_index']=min(st.session_state.get('reference_index',0),len(pool)-1)
    a,b=st.columns(2)
    a.button('← Previous',on_click=step_reference,args=(-1,len(pool)),width='stretch')
    b.button('Next →',on_click=step_reference,args=(1,len(pool)),width='stretch')
    idx=st.selectbox('Reference neuron',range(len(pool)),format_func=lambda i:pool[i]['metadata']['label'],key='reference_index')
    ref=pool[idx]; meta=ref['metadata']
    st.caption(f'{idx+1} of {len(pool)}')
    if meta.get('synthetic'):
        st.warning('Synthetic example — not an Allen neuron.')
    st.write(meta.get('species') or 'Unknown species')
    st.write(meta.get('region','Unknown region'))
    st.write(meta.get('cell_type','Unspecified cell label'))
    st.caption(f"Source: {meta.get('source','Unknown')} · Sweep {meta.get('sweep','?')}")
    if meta.get('source_url'):
        st.link_button('Source recording',meta['source_url'])
    with st.expander('Reference provenance'):
        st.json(meta)
with left:
    view=st.radio('Waveform',['AP spike','AHP'],horizontal=True)
    block='SPIKE' if view=='AP spike' else 'AHP'
    align_choice=st.radio('Align traces at',['Peak / trough','Onset'],horizontal=True,
                          help='Both traces place their own AP peak (or AHP trough) or event onset at 0 ms.')
    alignment='Event location' if align_choice=='Peak / trough' else 'Event onset'
    st.plotly_chart(overlay(query,ref,pool,block,alignment,normalize,highlight),width='stretch',key='overlay')
    st.caption('Black: your neuron · Gray: reference · Solid markers: yours · Dashed markers: reference. The selected alignment is centered at 0 ms; axes stay fixed within this filtered collection.')
    for event,label in [(query,'Your neuron'),(ref,'Reference')]:
        if block=='AHP' and not np.isfinite(event['measurements']['AHP Location (ms)']):
            st.warning(label+' AHP is unresolved: '+event['measurements'].get('Status','No trough found'))
        elif block=='AHP' and not np.isfinite(event['measurements']['AHP Width (ms)']):
            st.caption(label+': AHP recovery is truncated; width is unavailable.')
        if alignment=='Event onset' and not np.isfinite(event['measurements'].get(f'{block} Onset (ms)',np.nan)):
            st.caption(label+': onset alignment is unavailable.')
        if block=='SPIKE' and not np.isfinite(event['measurements'].get('SPIKE Onset (ms)',np.nan)):
            st.warning(label+': AP onset is unresolved; onset-dependent dynamics are unavailable. Adjust the dV/dt threshold if appropriate.')
        if normalize and not np.isfinite(event['measurements'].get('AP amplitude (mV)' if block=='SPIKE' else 'AHP amplitude from threshold (mV)',np.nan)):
            st.caption(label+': normalized waveform is unavailable because event amplitude is unresolved.')
    if query['settings'] != ref['settings']:
        st.caption('The upload and reference use different detection/window settings. Reference settings are preserved in its collection; regenerate it to match if needed.')
    qm,rm=metrics(query,block),metrics(ref,block)
    rows=[{'Dynamic':k,'Your neuron':qm[k],'Reference':rm[k],'Reference − yours':rm[k]-qm[k]} for k in qm]
    st.dataframe(pd.DataFrame(rows).style.format(precision=4,na_rep='Unresolved',subset=['Your neuron','Reference','Reference − yours']),hide_index=True,width='stretch')
    with st.expander('Absolute and relative marker times'):
        rows=[]
        for event,label in [(query,'Your neuron'),(ref,'Reference')]:
            r=event['measurements']; origin=r[f'{block} Location (ms)']
            for marker in MARKERS:
                value=r.get(f'{block} {marker} (ms)',np.nan)
                rows.append({'Neuron':label,'Marker':marker,'Sweep time (ms)':value,'Relative to event location (ms)':value-origin})
        st.dataframe(pd.DataFrame(rows),hide_index=True,width='stretch')
st.caption('Compare electrophysiological phenotypes. Reference labels describe their source evidence; waveform similarity does not establish molecular identity.')
