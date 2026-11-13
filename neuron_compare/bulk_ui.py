"""Batch upload, CSV export, and group selection in the Streamlit app."""
import hashlib
from dataclasses import asdict
import streamlit as st
from .core import Settings
from .bulk import (analyze_file, results_frame, export_frame, import_kinetics_csv,
                   compare_multiple_groups, pairwise_statistics, GROUP_COLORS, SIGNIFICANCE_METHODS,
                   VOLTAGE_MEASURE_ORDER)
from .group_selection_component import group_selection_grid
from .group_figure import combined_boxplots_png, combined_boxplots_pdf, standalone_waveform_png
from .group_waveform import prototype_figure, significant_waveform_pairs
from .ahp_resolution import ahp_resolution_analysis


@st.cache_data(max_entries=1024, show_spinner=False)
def compact_analysis(data, name, channel, settings):
    # Cache only the small scalar row, never parsed sweeps or waveform arrays.
    return analyze_file(data, name, channel, settings)


def render_bulk():
    st.subheader('Bulk Kinetics')
    st.write('Upload rheobase step recordings. Each file contributes the first AP/AHP from its first AP-generating sweep, in recording order.')
    grouped = st.checkbox('Assign groups during upload', value=False, key='bulk_group_mode',
                          help='Separate recordings into 2–6 groups. CSV Group values run from 0 to 5 and are auto-assigned in Compare Groups.')
    if grouped:
        group_count = st.select_slider('Number of upload groups', options=list(range(2, 7)),
                                       value=2, key='bulk_upload_group_count')
        columns = st.columns(min(group_count, 3))
        group_uploads = []
        for j in range(group_count):
            with columns[j % len(columns)]:
                group_uploads.append(st.file_uploader(
                    f'Group {j+1} recordings (Group = {j})',
                    type=['abf','axgd','axgx'], accept_multiple_files=True,
                    key=f'bulk_group_{j}'))
        uploaded = [(u, str(j)) for j, group in enumerate(group_uploads) for u in (group or [])]
    else:
        uploads = st.file_uploader('Bulk rheobase recordings', type=['abf','axgd','axgx'],
                                   accept_multiple_files=True, key='bulk_uploads')
        uploaded = [(u, None) for u in (uploads or [])]
    with st.expander('Bulk analysis settings'):
        channel = st.number_input('Bulk voltage channel rank (0-based)',0,32,0)
        height = st.number_input('Bulk minimum AP peak (mV)',value=-10.)
        prominence = st.number_input('Bulk minimum prominence (mV)',min_value=0.,value=20.)
        dvdt = st.number_input('Bulk onset dV/dt (mV/ms)',min_value=.1,value=20.)
        recovery = st.number_input('Bulk captured recovery after AP peak (ms)',min_value=1.,value=100.,
                                   help='Maximum post-peak search/capture duration; stops at the next AP or recording boundary.')
        trough_window = st.number_input('Bulk AHP trough search after AP half-fall (ms)',
                                        min_value=1.,max_value=Settings.ahp_trough_window_ms,
                                        value=Settings.ahp_trough_window_ms,step=1.,
                                        help='Search up to 30 ms after AP half-fall (the shared maximum). Shorter windows exclude later minima; inspect late troughs for slow drift.')
        post_injection = st.checkbox('Allow AHP recovery after injection ends', value=True,
                                     help='Use recorded post-step voltage to measure the AHP, without including later action potentials.')
        manual = st.checkbox('Set bulk injection window manually')
        start = st.number_input('Bulk injection start (ms)',min_value=0.,value=100.,disabled=not manual)
        end = st.number_input('Bulk injection end (ms)',min_value=0.,value=600.,disabled=not manual)
    settings = Settings(height=height,prominence=prominence,dvdt_threshold=dvdt,ahp_window_ms=recovery,
                        ahp_trough_window_ms=trough_window,ahp_post_injection=post_injection,
                        start_ms=start if manual else None,end_ms=end if manual else None)
    st.caption('AHP trough search and recovery are independently configurable. AP and AHP half widths = half-fall − half-rise. Average RMP is the equal-weighted mean of each sweep’s pre-injection voltage average, with the detected injection start or manually specified injection start used to define its baseline. Unresolved measurements remain blank.')
    files = []
    for i, (upload, group) in enumerate(uploaded):
        digest = hashlib.sha256(upload.getvalue()).hexdigest()
        # Include filename and upload position to distinguish duplicate names/content.
        files.append((f'{i+1}:{digest}:{upload.name}',upload,group))
    signature = (tuple((key,group) for key,_,group in files), tuple(asdict(settings).items()), int(channel))
    if st.button('Process files',disabled=not files,key='process_bulk'):
        rows = []
        progress = st.progress(0.,text='Processing recordings…')
        for i,(key,upload,group) in enumerate(files):
            row = compact_analysis(upload.getvalue(),upload.name,int(channel),settings)
            row['File ID'] = key
            if grouped:
                row['Group'] = group
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
                             export_frame(rows, include_groups=True).to_csv(index=False,na_rep='').encode('utf-8-sig'),
                             file_name='bulk_kinetics_absolute.csv',mime='text/csv',key='bulk_absolute_csv',width='stretch')
    relative.download_button('Download relative kinetics CSV',
                             export_frame(rows,relative=True,include_groups=True).to_csv(index=False,na_rep='').encode('utf-8-sig'),
                             file_name='bulk_kinetics_relative.csv',mime='text/csv',key='bulk_relative_csv',width='stretch')
    st.caption('Exports include measured average pre-injection RMP across available sweeps, AP onset Vm, raw AP peak and AHP trough Vm, and signed peak/trough differences from RMP, plus RMP sweep count. The original AP-onset-relative amplitudes remain. Relative timestamps place AP peak at 0 ms; voltages are unchanged. RMP is blank if no reliable injection start can be identified.')
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
    upload = st.file_uploader(
        'Upload previously exported kinetics CSV (optional)', type=['csv'],
        key='comparison_import_csv',
        help='Accepts the PCAP absolute or relative kinetics CSV, optionally with a Group column. '
             'Importing does not require uploading the original ABF files.'
    )
    if upload is not None:
        basis = st.selectbox(
            'Imported timestamp basis', ['Auto', 'Absolute', 'Relative'],
            help='Auto detects relative exports when all AP location values are zero. '
                 'Override this for unusual recordings.'
        )
        try:
            csv_bytes = upload.getvalue()
            rows, detected_basis = import_kinetics_csv(csv_bytes, upload.name, basis)
        except ValueError as err:
            st.error('Unable to import kinetics CSV: ' + str(err))
            return
        # A saved CSV becomes its own stable session dataset; original bulk
        # selections and file order cannot accidentally affect these groups.
        signature = ('uploaded-csv', hashlib.sha256(csv_bytes).hexdigest(), basis)
        batch = {'signature': signature, 'rows': rows}
        st.success(str(len(rows)) + ' previously analyzed recordings loaded '
                   + '(' + detected_basis.lower() + ' time coordinates).')
    elif batch is None:
        st.info('Upload a previously exported PCAP kinetics CSV here, or process '
                'recordings in Bulk Kinetics.')
        return
    else:
        st.caption('Using the current session\'s Bulk Kinetics results. '
                   'Upload a saved CSV above to compare a different dataset.')
    rows = batch['rows']
    eligible = [r for r in rows if r['Status'] in ('OK', 'Partial')]
    if len(eligible) < 2:
        st.info('At least two files with detected APs are needed for group comparison.')
        return
    signature = batch['signature']
    if st.session_state.get('comparison_batch_signature') != signature:
        st.session_state['comparison_batch_signature'] = signature
        assigned_indices = [int(str(row['Group']).strip()) for row in eligible
                            if str(row.get('Group', '')).strip() in tuple(str(j) for j in range(6))]
        st.session_state['comparison_group_count'] = max(2, max(assigned_indices, default=-1) + 1)
        st.session_state.pop('bulk_comparison', None)
        st.session_state['comparison_assignments'] = {
            str(row['File ID']): int(str(row['Group']))
            for row in eligible if str(row.get('Group', '')).strip() in tuple(str(j) for j in range(6))
        }
        st.session_state['comparison_assignment_signature'] = signature
        for key in list(st.session_state):
            if key.startswith('comparison_cell_') or key.startswith('comparison_name_'):
                del st.session_state[key]
    count = st.session_state.get('comparison_group_count', 2)
    count = st.select_slider('Number of comparison groups', options=list(range(2, 7)),
                             value=max(2, min(6, count)), key='comparison_group_count')

    sort_mode = st.radio('Filename ordering',
                         ['Upload order', 'Alphanumeric (A–Z)', 'Alphanumeric (Z–A)'],
                         horizontal=True, key='comparison_sort_order')
    import re
    def natural_key(row):
        return [int(part) if part.isdigit() else part.casefold()
                for part in re.split(r'(\\d+)', str(row['Filename']))]
    ordered = list(eligible)
    if sort_mode != 'Upload order':
        ordered.sort(key=natural_key, reverse=(sort_mode == 'Alphanumeric (Z–A)'))

    st.markdown('**Group names**')
    group_columns = st.columns(min(count, 4))
    group_names = []
    for j in range(count):
        default = 'Group ' + str(j+1)
        name = group_columns[j % len(group_columns)].text_input(
            'Group ' + str(j+1) + ' name',
            value=default,
            key='comparison_name_' + str(j))
        group_names.append(name.strip())
    if not all(group_names) or len({name.casefold() for name in group_names}) != count:
        st.warning('Give each group a unique, non-empty name before analyzing.')
        return

    # Persist assignments independently of UI sort order. Dataset changes reset
    # these, but changing sort/group labels does not alter a recording's group.
    assignments_key = 'comparison_assignments'
    if st.session_state.get('comparison_assignment_signature') != signature:
        st.session_state['comparison_assignment_signature'] = signature
        st.session_state[assignments_key] = {}
    existing = st.session_state.get(assignments_key, {})
    files = [{'id': str(row['File ID']), 'filename': str(row['Filename']),
              'sweep': str(row['Sweep']), 'status': str(row['Status'])}
             for row in ordered]
    # Changing groups or sort order creates a new component instance but the
    # assignment mapping is carried over to the replacement instance.
    group_data = group_selection_grid(
        files, existing, group_names, sort_mode=sort_mode,
        key='comparison_group_selector_' + hashlib.sha256(
            repr((signature, sort_mode, count, tuple(group_names))).encode()).hexdigest()[:12])
    if isinstance(group_data, dict):
        existing = {str(k): int(v) for k,v in group_data.items()
                    if str(k) in {f['id'] for f in files} and isinstance(v, (int, float)) and int(v) == v and -1 <= int(v) < count}
        st.session_state[assignments_key] = existing
    groups = {
        group_names[j]: [str(row['File ID']) for row in eligible
                         if existing.get(str(row['File ID']), -1) == j]
        for j in range(count)
    }
    st.caption(' · '.join(name + ': ' + str(len(ids)) for name, ids in groups.items()))
    active = {name: ids for name, ids in groups.items() if ids}
    significance_method = st.radio(
        'Significance method for plot brackets and asterisks',
        list(SIGNIFICANCE_METHODS), index=2, horizontal=True,
        key='comparison_significance_method',
        help='The selected method controls only the bracket labels. Every plot and statistical export reports all three p-values.'
    )
    selection = (signature, tuple((name, tuple(ids)) for name, ids in active.items()),
                 significance_method)
    if st.button('Analyze', key='analyze_groups'):
        try:
            compare_multiple_groups(rows, active, significance_method=significance_method)
        except ValueError as err:
            st.warning(str(err))
        else:
            st.session_state['bulk_comparison'] = selection
    if st.session_state.get('bulk_comparison') != selection:
        return
    figures, summary = compare_multiple_groups(rows, active, significance_method=significance_method)
    tests = pairwise_statistics(rows, active)
    normalized = prototype_figure(rows, active, tests, significance_method=significance_method)
    absolute = prototype_figure(
        rows, active, tests, significance_method=significance_method,
        voltage_mode='absolute')
    ahp_chart, ahp_counts, ahp_tests = ahp_resolution_analysis(rows, active)
    time_plots = [fig for fig in figures if fig.layout.yaxis.title.text.endswith('(ms)')]
    voltage_by_metric = {
        (fig.layout.meta or {}).get('measure', fig.layout.yaxis.title.text): fig
        for fig in figures if fig.layout.yaxis.title.text.endswith('(mV)')
    }
    voltage_plots = [voltage_by_metric[key] for key in VOLTAGE_MEASURE_ORDER
                     if key in voltage_by_metric]

    st.caption('Every waveform is a schematic interpolation through mean measured landmarks, '
               'not an average of raw traces. All timing landmarks are aligned to AP peak (t = 0 ms).')
    tabs = st.tabs(['Protowaveform', 'Kinetics Measurements', 'Voltage Measurements'])
    with tabs[0]:
        st.subheader('AP threshold-normalized protowaveforms')
        st.plotly_chart(normalized, width='stretch', key='group_prototype_normalized')
        st.caption('AP threshold is 0 mV for each recording. Positive AP amplitude '
                   'and negative AHP amplitude represent changes from that threshold.')
        try:
            st.download_button('Download normalized protowaveforms PNG',
                               standalone_waveform_png(normalized),
                               file_name='pcap_protowaveforms_normalized.png',
                               mime='image/png', key='download_normalized_prototype')
        except Exception as exc:
            st.warning('Normalized waveform export could not be generated: ' + str(exc))

        st.subheader('Raw membrane-voltage protowaveforms')
        if not any(trace.type == 'scatter' for trace in absolute.data):
            st.info('Absolute-voltage waveforms require AP peak Vm, AHP trough Vm '
                    'and AP amplitude in the newer PCAP CSV. Older 16-column exports '
                    'do not retain enough information to reconstruct these values.')
        else:
            st.plotly_chart(absolute, width='stretch', key='group_prototype_absolute')
            missing_groups = set(active) - {
                trace.name for trace in absolute.data
                if trace.type == 'scatter' and trace.mode == 'lines'}
            if missing_groups:
                st.warning('Raw membrane-voltage profiles unavailable for: ' +
                           ', '.join(sorted(missing_groups)) +
                           '. Missing absolute voltages are not estimated.')
            st.caption('Raw Vm uses the mean AP onset/threshold, mean AP peak Vm, and '
                       'mean AHP trough Vm for complete recordings within each group. '
                       'Intermediate voltages are interpolated between these voltage landmarks. '
                       'The curve is not an average of original ABF waveform samples.')
            try:
                st.download_button('Download raw-voltage protowaveforms PNG',
                                   standalone_waveform_png(absolute),
                                   file_name='pcap_protowaveforms_raw_voltage.png',
                                   mime='image/png', key='download_absolute_prototype')
            except Exception as exc:
                st.warning('Raw-voltage waveform export could not be generated: ' + str(exc))
        if len(active) > 2:
            st.subheader('Significant waveform landmarks')
            for mode in ('relative', 'absolute'):
                significant = significant_waveform_pairs(
                    tests, active, significance_method, voltage_mode=mode)
                st.caption('Threshold-normalized' if mode == 'relative'
                           else 'Raw membrane-voltage')
                if significant:
                    st.dataframe(significant, hide_index=True, width='stretch')
                else:
                    st.caption('No significant landmark comparisons under ' +
                               significance_method + '.')

    export_title = st.text_input(
        'Combined figure title (PNG/PDF)',
        value='', key='comparison_combined_title',
        placeholder='e.g., Effects of Nifedipine on AP/AHP Kinetics',
        help='Centered at the top of the exported comparison figures.'
    ).strip()

    def render_measurements(name, plots, suffix):
        st.subheader(name)
        st.caption('Boxplots show individual recordings and pairwise significance brackets. '
                   'Brackets use ' + significance_method +
                   '; captions report Welch, Benjamini-Hochberg, and Holm p-values. '
                   'Corrections cover all numerical metrics and group pairs.')
        if plots:
            left, right = st.columns(2)
            try:
                left.download_button('Download ' + name + ' PNG',
                    combined_boxplots_png(plots, title=export_title),
                    file_name='pcap_' + suffix + '.png', mime='image/png',
                    key='download_' + suffix + '_png')
            except Exception as exc:
                st.warning('PNG export failed: ' + str(exc))
            try:
                right.download_button('Download ' + name + ' PDF',
                    combined_boxplots_pdf(plots, title=export_title),
                    file_name='pcap_' + suffix + '.pdf', mime='application/pdf',
                    key='download_' + suffix + '_pdf')
            except Exception as exc:
                st.warning('PDF export failed: ' + str(exc))
            columns = st.columns(2)
            for i, fig in enumerate(plots):
                with columns[i % 2]:
                    st.plotly_chart(fig, width='stretch', key=suffix + '_plot_' + str(i))
        else:
            st.info('No ' + name.lower() + ' are available.')
        selected = summary.loc[summary['Measure'].isin(
            [(fig.layout.meta or {}).get('measure', fig.layout.yaxis.title.text)
             for fig in plots])]
        st.dataframe(selected, hide_index=True, width='stretch')

    with tabs[1]:
        render_measurements('Kinetics Measurements', time_plots, 'kinetics_measurements')
    with tabs[2]:
        st.caption('First: raw average RMP and AP onset Vm; next: raw AP peak and AHP trough Vm; '
                   'then: AP peak height and positive AHP trough depth relative to AP onset; '
                   'finally: signed AP peak and AHP trough voltages relative to average RMP. '
                   'Positive means above the chosen baseline; negative means below it.')
        render_measurements('Voltage Measurements', voltage_plots, 'voltage_measurements')
        st.subheader('AHP trough resolution')
        st.plotly_chart(ahp_chart, width='stretch', key='ahp_resolution_chart')
        st.caption('Resolved means an AHP trough was identified after an AP; '
                   'full AHP recovery is not required. No-AP and failed recordings '
                   'are excluded. The χ² analysis uses a group-by-resolution '
                   'contingency table. When expected counts are small, consider '
                   'Fisher exact (two groups) instead of the χ² approximation. '
                   'Recordings must be independent; unresolved detection is not '
                   'proof of absent physiological AHP.')
        st.dataframe(ahp_counts, hide_index=True, width='stretch')
        st.dataframe(ahp_tests, hide_index=True, width='stretch')
        st.download_button('Download AHP resolution counts CSV',
                           ahp_counts.to_csv(index=False).encode('utf-8-sig'),
                           file_name='ahp_resolution_counts.csv', mime='text/csv')
        st.download_button('Download AHP resolution statistics CSV',
                           ahp_tests.to_csv(index=False).encode('utf-8-sig'),
                           file_name='ahp_resolution_statistics.csv', mime='text/csv')

    st.subheader('All comparison statistics')
    st.caption('Two-sided Welch tests assume independent observations. '
               'Use paired or clustered analysis for repeated recordings '
               'from the same cell or animal.')
    st.dataframe(summary, hide_index=True, width='stretch')
    st.dataframe(tests, hide_index=True, width='stretch')
    st.download_button('Download statistical tests CSV',
                       tests.to_csv(index=False, na_rep='').encode('utf-8-sig'),
                       file_name='group_statistics.csv', mime='text/csv')
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
