"""Batch upload, CSV export, and group selection in the Streamlit app."""
import hashlib
from dataclasses import asdict
import streamlit as st
from .core import Settings
from .bulk import analyze_file, results_frame, compare_groups


@st.cache_data(max_entries=1024, show_spinner=False)
def compact_analysis(data, name, channel, settings):
    # Cache only the small scalar row, never parsed sweeps or waveform arrays.
    return analyze_file(data, name, channel, settings)


def render_bulk():
    st.subheader('Bulk Kinetics')
    st.write('Upload rheobase step recordings. Each file contributes the first AP/AHP from its first AP-generating sweep, in recording order.')
    uploads = st.file_uploader('Bulk rheobase recordings', type=['abf','axgd','axgx'],
                               accept_multiple_files=True, key='bulk_uploads')
    with st.expander('Bulk analysis settings'):
        channel = st.number_input('Bulk voltage channel rank (0-based)',0,32,0)
        height = st.number_input('Bulk minimum AP peak (mV)',value=-10.)
        prominence = st.number_input('Bulk minimum prominence (mV)',min_value=0.,value=20.)
        dvdt = st.number_input('Bulk onset dV/dt (mV/ms)',min_value=.1,value=20.)
        recovery = st.number_input('Bulk captured recovery after AP peak (ms)',min_value=1.,value=100.,
                                   help='Maximum post-peak search/capture duration; stops at the next AP or recording boundary.')
        trough_window = st.number_input('Bulk AHP trough search after AP half-fall (ms)',
                                        min_value=1.,max_value=100.,value=10.,step=1.,
                                        help='Search for the AHP minimum beyond AP half-fall. Increase for slower AHPs, but inspect late minima to avoid including slow drift.')
        post_injection = st.checkbox('Allow AHP recovery after injection ends', value=True,
                                     help='Use recorded post-step voltage to measure the AHP, without including later action potentials.')
        manual = st.checkbox('Set bulk injection window manually')
        start = st.number_input('Bulk injection start (ms)',min_value=0.,value=100.,disabled=not manual)
        end = st.number_input('Bulk injection end (ms)',min_value=0.,value=600.,disabled=not manual)
    settings = Settings(height=height,prominence=prominence,dvdt_threshold=dvdt,ahp_window_ms=recovery,
                        ahp_trough_window_ms=trough_window,ahp_post_injection=post_injection,
                        start_ms=start if manual else None,end_ms=end if manual else None)
    st.caption('AHP trough search and recovery are independently configurable. AP and AHP half widths = half-fall − half-rise. Unresolved troughs or half-recovery crossings remain blank instead of being guessed. Review unusually late AHP troughs against the raw trace.')
    files = []
    for i, upload in enumerate(uploads or []):
        digest = hashlib.sha256(upload.getvalue()).hexdigest()
        # Include filename and upload position to distinguish duplicate names/content.
        files.append((f'{i+1}:{digest}:{upload.name}',upload))
    signature = (tuple(key for key,_ in files), tuple(asdict(settings).items()), int(channel))
    if st.button('Process files',disabled=not files,key='process_bulk'):
        rows = []
        progress = st.progress(0.,text='Processing recordings…')
        for i,(key,upload) in enumerate(files):
            row = compact_analysis(upload.getvalue(),upload.name,int(channel),settings)
            row['File ID'] = key
            rows.append(row)
            progress.progress((i+1)/len(files),text=f'Processed {i+1} of {len(files)}')
        progress.empty()
        st.session_state['bulk_results'] = {'signature': signature, 'rows': rows}
    saved = st.session_state.get('bulk_results')
    if not saved or saved['signature'] != signature:
        st.info('Upload files and click Process files to create the CSV. Reprocess after changing files or analysis settings.')
        return None
    rows = saved['rows']
    frame = results_frame(rows)
    counts = frame['Status'].value_counts()
    st.success(f"{len(rows)} files processed · {counts.get('OK',0)} complete · {counts.get('Partial',0)} partial · {counts.get('No AP',0)} without APs · {counts.get('Error',0)} errors")
    st.download_button('Download kinetics CSV',frame.to_csv(index=False,na_rep='').encode('utf-8-sig'),
                       file_name='bulk_kinetics.csv',mime='text/csv',key='bulk_csv')
    return saved


def render_groups(batch):
    st.subheader('Compare Groups')
    if batch is None:
        st.info('Process recordings in Bulk Kinetics first, then assign files to two groups here.')
        return
    rows = batch['rows']
    eligible = [r for r in rows if r['Status'] in ('OK','Partial')]
    options = [r['File ID'] for r in eligible]
    labels = {r['File ID']: f"{i+1}. {r['Filename']} · Sweep {r['Sweep']} · {r['Status']}" for i,r in enumerate(eligible)}
    if len(options)<2:
        st.info('At least two files with detected APs are needed for a group comparison.')
        return
    for key in ('bulk_group1','bulk_group2'):
        if key in st.session_state:
            st.session_state[key] = [v for v in st.session_state[key] if v in options]
    a,b = st.columns(2)
    group1 = a.multiselect('Group 1 files',options,format_func=labels.get,key='bulk_group1')
    group2 = b.multiselect('Group 2 files',options,format_func=labels.get,key='bulk_group2')
    st.caption('Each file is one observation. Select disjoint groups; unselected files are excluded. Partial files contribute only resolved values. Box plots show boxes and whiskers; n is shown for each measure.')
    signature = (batch['signature'],tuple(group1),tuple(group2))
    if st.button('Analyze',key='analyze_groups'):
        try:
            compare_groups(rows,group1,group2)
        except ValueError as err:
            st.warning(str(err))
        else:
            st.session_state['bulk_comparison'] = signature
    if st.session_state.get('bulk_comparison') != signature:
        return
    figures, summary = compare_groups(rows,group1,group2)
    columns = st.columns(2)
    for i,fig in enumerate(figures):
        with columns[i%2]:
            st.plotly_chart(fig,width='stretch',key=f'bulk_box_{i}')
    st.dataframe(summary,hide_index=True,width='stretch')
    st.download_button('Download group summary CSV',summary.to_csv(index=False,na_rep='').encode('utf-8-sig'),
                       file_name='group_summary.csv',mime='text/csv')
    assigned = results_frame(rows)
    assigned = assigned[assigned['File ID'].isin(group1+group2)].copy()
    assigned.insert(2,'Group',assigned['File ID'].map(lambda key: 'Group 1' if key in group1 else 'Group 2'))
    st.download_button('Download grouped kinetics CSV',assigned.to_csv(index=False,na_rep='').encode('utf-8-sig'),
                       file_name='grouped_kinetics.csv',mime='text/csv')
