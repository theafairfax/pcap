"""Batch upload, CSV export, and group selection in the Streamlit app."""
import hashlib
from dataclasses import asdict
import streamlit as st
from .core import Settings
from .bulk import analyze_file, results_frame, export_frame, compare_multiple_groups, GROUP_COLORS


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
    absolute, relative = st.columns(2)
    absolute.download_button('Download absolute kinetics CSV',
                             export_frame(rows).to_csv(index=False,na_rep='').encode('utf-8-sig'),
                             file_name='bulk_kinetics_absolute.csv',mime='text/csv',key='bulk_absolute_csv',width='stretch')
    relative.download_button('Download relative kinetics CSV',
                             export_frame(rows,relative=True).to_csv(index=False,na_rep='').encode('utf-8-sig'),
                             file_name='bulk_kinetics_relative.csv',mime='text/csv',key='bulk_relative_csv',width='stretch')
    st.caption('Both exports use the 16-column worksheet. Relative timestamps have AP peak = 0 ms. AHP Half-Fall is the descending midpoint crossing before the trough.')
    return saved


def _cell_key(file_id, index):
    return 'comparison_cell_' + hashlib.sha256(
        (str(file_id) + ':' + str(index)).encode('utf-8')).hexdigest()[:20]


def _exclusive_group_assignment(file_id, index, count):
    """Only one checked group per file; unchecking leaves a file unassigned."""
    key = _cell_key(file_id, index)
    if st.session_state.get(key, False):
        for other in range(count):
            if other != index:
                st.session_state[_cell_key(file_id, other)] = False


def render_groups(batch):
    st.subheader('Compare Groups')
    if batch is None:
        st.info('Process recordings in Bulk Kinetics first, then assign files here.')
        return
    rows = batch['rows']
    eligible = [r for r in rows if r['Status'] in ('OK', 'Partial')]
    if len(eligible) < 2:
        st.info('At least two files with detected APs are needed for group comparison.')
        return
    signature = batch['signature']
    if st.session_state.get('comparison_batch_signature') != signature:
        st.session_state['comparison_batch_signature'] = signature
        st.session_state['comparison_group_count'] = 2
        st.session_state.pop('bulk_comparison', None)
        for key in list(st.session_state):
            if key.startswith('comparison_cell_'):
                del st.session_state[key]
    count = st.session_state.get('comparison_group_count', 2)
    if st.button('Add another group', key='add_comparison_group'):
        count += 1
        st.session_state['comparison_group_count'] = count
        st.session_state.pop('bulk_comparison', None)
    st.caption('Assign each recording using the colored group checkbox beside its filename. A recording can be in only one group; unchecked files are excluded.')
    headings = st.columns([4] + [1] * count)
    headings[0].markdown('**Analyzed filename**')
    for j in range(count):
        color = GROUP_COLORS[j % len(GROUP_COLORS)]
        headings[j+1].markdown('<span style="color:' + color + '"><b>Group ' + str(j+1) + '</b></span>', unsafe_allow_html=True)
    for i, item in enumerate(eligible):
        cells = st.columns([4] + [1] * count)
        cells[0].write(str(i+1) + '. ' + str(item['Filename']) + ' · Sweep ' + str(item['Sweep']) + ' · ' + str(item['Status']))
        for j in range(count):
            with cells[j+1]:
                st.checkbox('Group ' + str(j+1) + ' for file ' + str(i+1),
                            key=_cell_key(item['File ID'], j), label_visibility='collapsed',
                            on_change=_exclusive_group_assignment,
                            args=(item['File ID'], j, count))
    groups = {}
    for j in range(count):
        members = [r['File ID'] for r in eligible if st.session_state.get(_cell_key(r['File ID'], j), False)]
        groups['Group ' + str(j+1)] = members
    st.caption(' · '.join(name + ': ' + str(len(members)) for name, members in groups.items()))
    active = {name: ids for name, ids in groups.items() if ids}
    selection = (signature, tuple((name, tuple(ids)) for name, ids in active.items()))
    if st.button('Analyze', key='analyze_groups'):
        try:
            compare_multiple_groups(rows, active)
        except ValueError as err:
            st.warning(str(err))
        else:
            st.session_state['bulk_comparison'] = selection
    if st.session_state.get('bulk_comparison') != selection:
        return
    figures, summary = compare_multiple_groups(rows, active)
    columns = st.columns(2)
    for i, fig in enumerate(figures):
        with columns[i % 2]:
            st.plotly_chart(fig, width='stretch', key='bulk_box_' + str(i))
    st.dataframe(summary, hide_index=True, width='stretch')
    st.download_button('Download group summary CSV',
                       summary.to_csv(index=False, na_rep='').encode('utf-8-sig'),
                       file_name='group_summary.csv', mime='text/csv')
    assigned = export_frame(rows, relative=True)
    full = results_frame(rows)
    labels = {file_id: name for name, ids in active.items() for file_id in ids}
    assigned.insert(1, 'Group', full['File ID'].map(labels))
    assigned = assigned[assigned['Group'].notna()]
    st.download_button('Download grouped relative kinetics CSV',
                       assigned.to_csv(index=False, na_rep='').encode('utf-8-sig'),
                       file_name='grouped_kinetics_relative.csv', mime='text/csv')
