"""Compact per-file kinetics and descriptive two-group comparisons."""
from dataclasses import asdict
import json
import numpy as np
import pandas as pd
import plotly.graph_objects as go
from .core import ANALYSIS_VERSION, MARKERS, Settings, count_spikes, first_event, injection_window, metrics
from .recordings import load_recording

STANDARD_METRICS = ('Peak Vm (mV)', 'Amplitude from AP threshold (mV)',
                    'Onset relative to event location (ms)', 'Rise 10–90% (ms)', 'Half width (ms)')
KINETIC_COLUMNS = ([f'AP {name}' for name in STANDARD_METRICS]
                   + [f'AHP {name}' for name in ('Trough Vm (mV)',)+STANDARD_METRICS[1:]]
                   + ['AP peak to AHP trough (ms)', 'AHP onset time (ms)', 'AHP trough time (ms)',
                      'AHP trough voltage (mV)', 'AHP half-fall time (ms)',
                      'AHP rebound time (ms)', 'AHP rebound latency from trough (ms)'])
MARKER_COLUMNS = ([f'AP {marker} (ms)' for marker in MARKERS if marker != 'Rebound']
                  + [f'AHP {marker} (ms)' for marker in MARKERS])
COLUMNS = (['File ID','Filename','Status','Detail','Sweep','APs in selected sweep','Analysis version',
            'Voltage channel rank','Analysis settings','Injection start (ms)','Injection end (ms)',
            'Injection window source','Sampling Rate (Hz)','Average RMP (mV)',
            'RMP sweeps used','AP threshold Vm (mV)',
            'AP peak relative to avg RMP (mV)', 'AHP trough relative to avg RMP (mV)']
           + KINETIC_COLUMNS + MARKER_COLUMNS)


def average_rmp(sweeps, settings=Settings()):
    """Mean of per-sweep pre-injection mean voltages (mV), with equal sweep weight.

    Locate each current-step onset using the same detector as AP analysis.
    Apply the median detected onset to zero-current/silent sweeps.
    A manual injection start takes precedence. With no reliable timing,
    return missing rather than assume a resting baseline.
    """
    detected_starts = {}
    for sweep in sweeps:
        try:
            start, _, source = injection_window(sweep, Settings())
        except (ValueError, IndexError):
            continue
        if source == 'Current-derived injection window' and start > float(sweep.time[0]):
            detected_starts[sweep.index] = start - float(sweep.time[0])
    common_start = (settings.start_ms / 1000. if settings.start_ms is not None
                    else float(np.median(list(detected_starts.values())))
                    if detected_starts else np.nan)
    baselines = []
    for sweep in sweeps:
        duration = (settings.start_ms / 1000. if settings.start_ms is not None
                    else detected_starts.get(sweep.index, common_start))
        if not np.isfinite(duration) or duration <= 0:
            continue
        first_injection_sample = int(np.searchsorted(
            sweep.time, float(sweep.time[0]) + duration, side='left'))
        if first_injection_sample < 2:
            continue
        baseline = np.asarray(sweep.voltage[:first_injection_sample], dtype=float)
        if np.all(np.isfinite(baseline)):
            baselines.append(float(np.mean(baseline)))
    return (float(np.mean(baselines)) if baselines else np.nan, len(baselines))


def analyze_file(data, filename, channel=0, settings=Settings()):
    """Read one recording, retain only scalars, and never skip a partial first AP."""
    row = dict.fromkeys(COLUMNS, np.nan)
    row.update(Filename=filename, Status='Error', Detail='', **{
        'Analysis version': ANALYSIS_VERSION, 'Voltage channel rank': channel,
        'Analysis settings': json.dumps(asdict(settings), sort_keys=True)})
    try:
        sweeps = load_recording(data, filename, channel)
        rmp, rmp_n = average_rmp(sweeps, settings)
        row['Average RMP (mV)'], row['RMP sweeps used'] = rmp, rmp_n
        selected = None
        for sweep in sweeps:
            count = count_spikes(sweep, settings)
            if count:
                selected = sweep
                break
        if selected is None:
            row.update(Status='No AP', Detail='No AP detected in any sweep injection window.')
            return row
        event = first_event(selected, settings)
        r, meta = event['measurements'], event['metadata']
        row.update({'Sweep': selected.index, 'Sampling Rate (Hz)': float(1. / np.median(np.diff(selected.time))),
                    'APs in selected sweep': count,
                    'Injection start (ms)': meta['injection_start_ms'],
                    'Injection end (ms)': meta['injection_end_ms'],
                    'Injection window source': meta['window_source'],
                    'AP threshold Vm (mV)': r['Threshold Vm (mV)'],
                    'AP peak relative to avg RMP (mV)':
                        r['SPIKE Peak Membrane Voltage-1 (mV)'] - rmp,
                    'AHP trough relative to avg RMP (mV)':
                        r['AHP trough Vm (mV)'] - rmp})
        for block, label in (('SPIKE','AP'), ('AHP','AHP')):
            for name, value in metrics(event, block).items():
                if name.startswith('AHP ') and name in KINETIC_COLUMNS:
                    row[name] = value
                elif name == 'AP peak to trough (ms)':
                    row['AP peak to AHP trough (ms)'] = value
                elif name == 'Half-height width (ms)':
                    # Explicitly use the two half-height crossings for both events.
                    row[f'{label} Half width (ms)'] = r.get(f'{block} Half fall (ms)',np.nan)-r.get(f'{block} Half rise (ms)',np.nan)
                else:
                    row[f'{label} {name}'] = value
            for marker in MARKERS:
                row[f'{label} {marker} (ms)'] = r.get(f'{block} {marker} (ms)', np.nan)
        required = [c for c in KINETIC_COLUMNS if 'rebound' not in c.lower()]
        row['Status'] = 'OK' if all(np.isfinite(row[c]) for c in required) else 'Partial'
        row['Detail'] = r['Status']
    except Exception as err:
        row.update(Status='Error', Detail=str(err))
    return row


def results_frame(rows):
    return pd.DataFrame(rows, columns=COLUMNS)


# Publication-oriented export schema: preserve existing fields and append
# directly measured voltage baselines and RMP-referenced differences.
VOLTAGE_EXPORT_COLUMNS = [
    'Average RMP (mV)', 'AP onset Vm (mV)', 'AP peak Vm (mV)',
    'AHP trough Vm (mV)', 'AP peak relative to avg RMP (mV)',
    'AHP trough relative to avg RMP (mV)',
]
RMP_METADATA_COLUMNS = ['RMP sweeps used']
LEGACY_EXPORT_COLUMNS = [
    'Filename', 'Sampling Rate (Hz)', 'Sweep', 'AP Location (ms)',
    'AP Onset (ms)', 'AP Rise 10% (ms)', 'AP Rise 90% (ms)',
    'AP rise time (ms)', 'AP Half rise (ms)', 'AP Half fall (ms)',
    'AP Half width (ms)', 'AHP Location (ms)', 'AHP Onset (ms)',
    'AHP Half-Fall (ms)', 'AP amplitude (mV)', 'AHP amplitude (mV)',
]
EXPORT_COLUMNS = LEGACY_EXPORT_COLUMNS + VOLTAGE_EXPORT_COLUMNS + RMP_METADATA_COLUMNS
# Only coordinate timestamps are shifted; elapsed durations and voltages are not.
EXPORT_TIMES = [
    'AP Location (ms)', 'AP Onset (ms)', 'AP Rise 10% (ms)',
    'AP Rise 90% (ms)', 'AP Half rise (ms)', 'AP Half fall (ms)',
    'AHP Location (ms)', 'AHP Onset (ms)', 'AHP Half-Fall (ms)',
]
# Group comparisons use AP-peak-relative timestamps and raw/offset voltages.
# RMP sweep count is metadata, not a statistical hypothesis.
COMPARISON_COLUMNS = [
    c for c in EXPORT_COLUMNS if c not in ('Filename', 'Sampling Rate (Hz)',
                                         'Sweep', 'AP Location (ms)', 'RMP sweeps used')
]
VOLTAGE_MEASURE_ORDER = (
    'Average RMP (mV)', 'AP onset Vm (mV)',
    'AP peak Vm (mV)', 'AHP trough Vm (mV)',
    'AP amplitude (mV)', 'AHP amplitude (mV)',
    'AP peak relative to avg RMP (mV)', 'AHP trough relative to avg RMP (mV)',
)
DISPLAY_TITLES = {
    'AP amplitude (mV)': 'AP peak above AP onset (mV)',
    'AHP amplitude (mV)': 'AHP trough depth below AP onset (mV)',
}
GROUP_COLORS = ('#475569', '#dc645b', '#16a085', '#8266b0', '#d09431',
                '#337db8', '#b76591', '#7c8a4b')


def export_frame(rows, relative=False, include_groups=False):
    """Build a concise export without modifying the underlying analysis rows."""
    frame = results_frame(rows)
    out = pd.DataFrame(index=frame.index)
    mapping = {
        'AP Location (ms)': 'AP Location (ms)',
        'AP Onset (ms)': 'AP Onset (ms)',
        'AP Rise 10% (ms)': 'AP Rise 10% (ms)',
        'AP Rise 90% (ms)': 'AP Rise 90% (ms)',
        'AP rise time (ms)': 'AP Rise 10–90% (ms)',
        'AP Half rise (ms)': 'AP Half rise (ms)',
        'AP Half fall (ms)': 'AP Half fall (ms)',
        'AP Half width (ms)': 'AP Half width (ms)',
        'AHP Location (ms)': 'AHP Location (ms)',
        'AHP Onset (ms)': 'AHP Onset (ms)',
        # Descending midpoint between onset/threshold and trough; this does
        # not require AHP recovery. The legacy internal name is Half rise.
        'AHP Half-Fall (ms)': 'AHP Half rise (ms)',
        'Average RMP (mV)': 'Average RMP (mV)',
        'AP onset Vm (mV)': 'AP threshold Vm (mV)',
        'AP peak Vm (mV)': 'AP Peak Vm (mV)',
        'AHP trough Vm (mV)': 'AHP Trough Vm (mV)',
        'AP peak relative to avg RMP (mV)': 'AP peak relative to avg RMP (mV)',
        'AHP trough relative to avg RMP (mV)': 'AHP trough relative to avg RMP (mV)',
        'RMP sweeps used': 'RMP sweeps used',
        'AP amplitude (mV)': 'AP Amplitude from AP threshold (mV)',
        # Report positive hyperpolarization depth (threshold - trough).
        'AHP amplitude (mV)': 'AHP Amplitude from AP threshold (mV)',
    }
    for column in EXPORT_COLUMNS:
        if column in ('Filename', 'Sampling Rate (Hz)', 'Sweep'):
            out[column] = frame[column]
        else:
            out[column] = pd.to_numeric(frame[mapping[column]], errors='coerce')
    out['AHP amplitude (mV)'] = -out['AHP amplitude (mV)']
    if relative:
        peak = pd.to_numeric(frame['AP Location (ms)'], errors='coerce')
        for column in EXPORT_TIMES:
            out[column] = out[column] - peak
    if include_groups and any('Group' in row for row in rows):
        group = pd.Series([row.get('Group', '') for row in rows]).map(lambda value: '' if pd.isna(value) else str(value).strip())
        if group.ne('').any():
            out.insert(1, 'Group', group)
    return out



def import_kinetics_csv(data, filename='previous_export.csv', timing='Auto'):
    """Parse prior PCAP exports and the expanded RMP/onset schema.

    Imports never re-run electrophysiology extraction. Absolute timestamps
    are converted to AP-peak-relative only when producing comparisons.
    """
    import io
    if timing not in ('Auto', 'Absolute', 'Relative'):
        raise ValueError('Time basis must be Auto, Absolute or Relative.')
    try:
        source = pd.read_csv(io.BytesIO(data), encoding='utf-8-sig')
    except Exception as exc:
        raise ValueError('Cannot read the uploaded CSV: ' + str(exc)) from exc
    source.columns = [str(c).strip() for c in source.columns]
    if source.columns.duplicated().any():
        raise ValueError('CSV contains duplicate column names.')
    # Older PCAP exports lack raw Vm: keep them importable, but do not
    # fabricate absolute voltages from amplitudes without a threshold Vm.
    missing = [name for name in LEGACY_EXPORT_COLUMNS if name not in source]
    if missing:
        raise ValueError('Missing required PCAP export columns: ' + ', '.join(missing))
    group_values = None
    if 'Group' in source:
        group_values = source['Group'].fillna('').astype(str).str.strip()
        allowed = {'', *map(str, range(6)), 'True', 'False', 'true', 'false'}
        if not set(group_values.unique()) <= allowed:
            raise ValueError('Group must contain 0–5 or legacy True/False (or be blank).')
        group_values = group_values.replace({'True':'1','true':'1','False':'0','false':'0'})
    if len(source) == 0:
        raise ValueError('Uploaded kinetics CSV contains no recordings.')
    if source['Filename'].isna().any() or source['Filename'].astype(str).str.strip().eq('').any():
        raise ValueError('Each CSV row needs a filename.')
    # The relative export uses zero-valued AP peak timestamps. For files
    # where detection is ambiguous, manual selection overrides Auto.
    peaks = pd.to_numeric(source['AP Location (ms)'], errors='coerce')
    inferred = 'Relative' if peaks.notna().all() and np.all(np.abs(peaks.to_numpy()) < 1e-6) else 'Absolute'
    actual_basis = inferred if timing == 'Auto' else timing
    numeric = {}
    for col in EXPORT_COLUMNS:
        if col != 'Filename' and col in source:
            numeric[col] = pd.to_numeric(source[col], errors='coerce')
            nonblank = source[col].notna() & source[col].astype(str).str.strip().ne('')
            invalid = nonblank & numeric[col].isna()
            if invalid.any():
                raise ValueError('Non-numeric values found in column: ' + col)
    rows = []
    column_map = {
        'AP Location (ms)': 'AP Location (ms)',
        'AP Onset (ms)': 'AP Onset (ms)',
        'AP Rise 10% (ms)': 'AP Rise 10% (ms)',
        'AP Rise 90% (ms)': 'AP Rise 90% (ms)',
        'AP rise time (ms)': 'AP Rise 10–90% (ms)',
        'AP Half rise (ms)': 'AP Half rise (ms)',
        'AP Half fall (ms)': 'AP Half fall (ms)',
        'AP Half width (ms)': 'AP Half width (ms)',
        'AHP Location (ms)': 'AHP Location (ms)',
        'AHP Onset (ms)': 'AHP Onset (ms)',
        # Descending AHP crossing is stored under the legacy measurement key.
        'AHP Half-Fall (ms)': 'AHP Half rise (ms)',
        'AP amplitude (mV)': 'AP Amplitude from AP threshold (mV)',
        'AP peak Vm (mV)': 'AP Peak Vm (mV)',
        'AHP trough Vm (mV)': 'AHP Trough Vm (mV)',
        'Average RMP (mV)': 'Average RMP (mV)',
        'AP onset Vm (mV)': 'AP threshold Vm (mV)',
        'AP peak relative to avg RMP (mV)': 'AP peak relative to avg RMP (mV)',
        'AHP trough relative to avg RMP (mV)': 'AHP trough relative to avg RMP (mV)',
        'RMP sweeps used': 'RMP sweeps used',
    }
    for position in range(len(source)):
        row = dict.fromkeys(COLUMNS, np.nan)
        label = str(source.iloc[position]['Filename']).strip()
        row.update({
            'File ID': 'csv:' + str(position) + ':' + label,
            'Filename': label, 'Status': 'OK',
            'Detail': 'Imported PCAP CSV (' + actual_basis.lower() + ' timestamps)',
            'Sweep': numeric['Sweep'].iloc[position],
            'Sampling Rate (Hz)': numeric['Sampling Rate (Hz)'].iloc[position],
        })
        if group_values is not None:
            row['Group'] = group_values.iloc[position]
        for key, dest in column_map.items():
            row[dest] = numeric[key].iloc[position] if key in numeric else np.nan
        depth = numeric['AHP amplitude (mV)'].iloc[position]
        row['AHP Amplitude from AP threshold (mV)'] = -depth if pd.notna(depth) else np.nan
        if any(pd.isna(numeric[k].iloc[position]) for k in LEGACY_EXPORT_COLUMNS if k in COMPARISON_COLUMNS):
            row['Status'] = 'Partial'
        rows.append(row)
    return rows, actual_basis


def _holm_adjust(pvalues):
    """Holm family-wise correction for all valid pairwise metric tests."""
    out = [np.nan] * len(pvalues)
    indices = sorted((i for i, value in enumerate(pvalues) if np.isfinite(value)),
                     key=lambda i: pvalues[i])
    maximum = 0.
    for rank, index in enumerate(indices):
        maximum = max(maximum, min(1., pvalues[index] * (len(indices) - rank)))
        out[index] = maximum
    return out


def _bh_adjust(pvalues):
    """Benjamini-Hochberg correction across all finite hypothesis tests."""
    out = [np.nan] * len(pvalues)
    indices = sorted((i for i, p in enumerate(pvalues) if np.isfinite(p)), key=lambda i: pvalues[i])
    minimum = 1.
    for rank in range(len(indices) - 1, -1, -1):
        index = indices[rank]
        minimum = min(minimum, float(pvalues[index]) * len(indices) / (rank + 1))
        out[index] = minimum
    return out


SIGNIFICANCE_METHODS = {
    "Welch's t-test (uncorrected)": 'Welch p-value',
    'Benjamini-Hochberg (FDR)': 'BH-adjusted p-value',
    'Holm-Bonferroni': 'Holm-adjusted p-value',
}


def _p_text(value):
    return 'N/A' if not np.isfinite(value) else ('<0.001' if value < .001 else f'{value:.3f}')


def _comparison_caption(row):
    return (f"{row['Group A']} vs {row['Group B']}: "
            f"Welch p={_p_text(row['Welch p-value'])}; "
            f"BH FDR p={_p_text(row['BH-adjusted p-value'])}; "
            f"Holm p={_p_text(row['Holm-adjusted p-value'])}")


def pairwise_statistics(rows, groups):
    """Welch independent-samples tests; family-wide Holm-adjusted p-values."""
    from itertools import combinations
    from scipy.stats import ttest_ind
    indexed = results_frame(rows).set_index('File ID', drop=False)
    relative = export_frame(rows, relative=True)
    relative.index = indexed.index
    tests = []
    for measure in COMPARISON_COLUMNS:
        for (first, first_ids), (second, second_ids) in combinations(groups.items(), 2):
            a = pd.to_numeric(relative.loc[list(first_ids), measure], errors='coerce')
            b = pd.to_numeric(relative.loc[list(second_ids), measure], errors='coerce')
            a = a[np.isfinite(a)].to_numpy(dtype=float)
            b = b[np.isfinite(b)].to_numpy(dtype=float)
            # Two independent observations per group are required to estimate
            # an unpooled variance; zero variance in both groups is undefined.
            p = np.nan
            if len(a) >= 2 and len(b) >= 2:
                with np.errstate(invalid='ignore', divide='ignore'):
                    p = float(ttest_ind(a, b, equal_var=False).pvalue)
            tests.append({
                'Measure': measure, 'Group A': first, 'Group B': second,
                'n A': len(a), 'n B': len(b),
                'Mean A': float(np.mean(a)) if len(a) else np.nan,
                'Mean B': float(np.mean(b)) if len(b) else np.nan,
                'Welch p-value': p,
            })
    adjusted = _holm_adjust([entry['Welch p-value'] for entry in tests])
    bh_adjusted = _bh_adjust([entry['Welch p-value'] for entry in tests])
    for entry, p, bh in zip(tests, adjusted, bh_adjusted):
        entry['Holm-adjusted p-value'] = p
        entry['BH-adjusted p-value'] = bh
    return pd.DataFrame(tests)


def significance_label(p):
    """Publication-style stars based on the Holm-adjusted p-value."""
    if not np.isfinite(p):
        return 'N/A'
    if p < .001:
        return '***'
    if p < .01:
        return '**'
    if p < .05:
        return '*'
    return 'n.s.'


def comparison_brackets(fig, relevant, group_names, values, significance_column='Holm-adjusted p-value'):
    """Add pairwise Plotly brackets above the highest finite observations."""
    if not values or not any(len(a) for a in values):
        return
    finite = np.concatenate([a for a in values if len(a)])
    low, high = float(finite.min()), float(finite.max())
    span = high - low
    step = span * .12 if span > 0 else max(abs(high) * .12, 1.)
    base = high + step * .55
    names = {name: i for i, name in enumerate(group_names)}
    pairs = []
    for _, result in relevant.iterrows():
        left, right = sorted((names[result['Group A']], names[result['Group B']]))
        pairs.append((right - left, left, right, result))
    # Draw short connections first, keeping longer spanning comparisons higher.
    pairs.sort(key=lambda p: (p[0], p[1], p[2]))
    levels = []
    for _, left, right, result in pairs:
        level = 0
        while level < len(levels) and any(not (right < a or left > b) for a, b in levels[level]):
            level += 1
        if level == len(levels):
            levels.append([])
        levels[level].append((left, right))
        y = base + step * 1.15 * level
        tick = step * .25
        fig.add_shape(type='path', xref='x', yref='y',
                      path=f'M {left} {y-tick} L {left} {y} L {right} {y} L {right} {y-tick}',
                      line=dict(color='#334155', width=1.25))
        fig.add_annotation(x=(left + right) / 2, y=y + step * .12,
                           xref='x', yref='y', text=significance_label(result[significance_column]),
                           showarrow=False, yanchor='bottom', font=dict(size=12, color='#111827'))
    ceiling = base + step * (1.15 * max(0, len(levels) - 1) + .9)
    fig.update_yaxes(range=[low - step * .55, ceiling])


def compare_multiple_groups(rows, groups, significance_method='Holm-Bonferroni'):
    """Compare disjoint groups using relative landmarks and unchanged kinetics.

    `groups` maps display names to collections of stable File IDs.
    """
    if significance_method not in SIGNIFICANCE_METHODS:
        raise ValueError('Unknown significance correction: ' + str(significance_method))
    significance_column = SIGNIFICANCE_METHODS[significance_method]
    groups = {str(name): list(ids) for name, ids in groups.items()}
    if not 2 <= len(groups) <= 6 or any(not ids for ids in groups.values()):
        raise ValueError('Assign at least one file to each of 2–6 groups.')
    flattened = [file_id for ids in groups.values() for file_id in ids]
    if len(flattened) != len(set(flattened)):
        raise ValueError('A recording can only be assigned to one group.')
    indexed = results_frame(rows).set_index('File ID', drop=False)
    if not set(flattened) <= set(indexed.index):
        raise ValueError('Group assignments must come from the current analysis.')
    rel = export_frame(rows, relative=True)
    rel.index = indexed.index
    tests = pairwise_statistics(rows, groups)
    figures, summary = [], []
    for measure in COMPARISON_COLUMNS:
        fig = go.Figure()
        subtitle = []
        measurements = []
        for n, (name, ids) in enumerate(groups.items()):
            numeric = pd.to_numeric(rel.loc[ids, measure], errors='coerce')
            valid = numeric[np.isfinite(numeric)]
            measurements.append(valid.to_numpy(dtype=float))
            subtitle.append(f'{name} n={len(valid)}')
            color = GROUP_COLORS[n % len(GROUP_COLORS)]
            fig.add_trace(go.Box(y=valid.tolist(), name=name, boxpoints='all', jitter=.32,
                                 pointpos=0, marker=dict(color=color, size=5, opacity=.88),
                                 line=dict(color=color), fillcolor=color, opacity=.70))
            summary.append({
                'Measure': measure, 'Group': name, 'n': len(valid),
                'Missing': len(ids) - len(valid),
                'Mean': valid.mean(), 'Median': valid.median(),
                'SD': valid.std(ddof=1),
            })
        relevant = tests.loc[tests['Measure'].eq(measure)]
        comparisons = [_comparison_caption(r) for _, r in relevant.iterrows()]
        comparison_brackets(fig, relevant, list(groups), measurements,
                            significance_column=significance_column)
        fig.update_layout(title=f"{measure}<br><sup>{' · '.join(subtitle)}</sup>",
                          yaxis_title=measure, template='plotly_white',
                          height=390 + 22 * max(0, len(comparisons)-1),
                          margin=dict(l=20, r=20, t=75, b=100 + 19 * max(0, len(comparisons)-1)))
        fig.add_annotation(x=.5, y=-.22, xref='paper', yref='paper',
                           text='<br>'.join(comparisons), showarrow=False,
                           xanchor='center', yanchor='top',
                           font=dict(size=10))
        figures.append(fig)
    return figures, pd.DataFrame(summary)


def compare_groups(rows, group1, group2):
    """Backward-compatible two-group interface, now using relative timestamps."""
    return compare_multiple_groups(rows, {'Group 1': group1, 'Group 2': group2})
