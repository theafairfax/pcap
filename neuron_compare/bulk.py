"""Compact per-file kinetics and descriptive two-group comparisons."""
from dataclasses import asdict
import json
import numpy as np
import pandas as pd
import plotly.graph_objects as go
from .core import ANALYSIS_VERSION, MARKERS, Settings, count_spikes, first_event, metrics
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
            'Injection window source','Sampling Rate (Hz)','AP threshold Vm (mV)'] + KINETIC_COLUMNS + MARKER_COLUMNS)


def analyze_file(data, filename, channel=0, settings=Settings()):
    """Read one recording, retain only scalars, and never skip a partial first AP."""
    row = dict.fromkeys(COLUMNS, np.nan)
    row.update(Filename=filename, Status='Error', Detail='', **{
        'Analysis version': ANALYSIS_VERSION, 'Voltage channel rank': channel,
        'Analysis settings': json.dumps(asdict(settings), sort_keys=True)})
    try:
        sweeps = load_recording(data, filename, channel)
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
                    'AP threshold Vm (mV)': r['Threshold Vm (mV)']})
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


# Publication-oriented 16-column export schema from the supplied worksheet.
EXPORT_COLUMNS = [
    'Filename', 'Sampling Rate (Hz)', 'Sweep', 'AP Location (ms)',
    'AP Onset (ms)', 'AP Rise 10% (ms)', 'AP Rise 90% (ms)',
    'AP rise time (ms)', 'AP Half rise (ms)', 'AP Half fall (ms)',
    'AP Half width (ms)', 'AHP Location (ms)', 'AHP Onset (ms)',
    'AHP Half-Fall (ms)', 'AP amplitude (mV)', 'AHP amplitude (mV)',
]
# Only coordinate timestamps are shifted; elapsed durations and voltages are not.
EXPORT_TIMES = [
    'AP Location (ms)', 'AP Onset (ms)', 'AP Rise 10% (ms)',
    'AP Rise 90% (ms)', 'AP Half rise (ms)', 'AP Half fall (ms)',
    'AHP Location (ms)', 'AHP Onset (ms)', 'AHP Half-Fall (ms)',
]
# Group comparisons use AP-peak-relative landmark times and unchanged duration/amplitude.
COMPARISON_COLUMNS = [
    c for c in EXPORT_COLUMNS if c not in ('Filename', 'Sampling Rate (Hz)', 'Sweep', 'AP Location (ms)')
]
GROUP_COLORS = ('#475569', '#dc645b', '#16a085', '#8266b0', '#d09431',
                '#337db8', '#b76591', '#7c8a4b')


def export_frame(rows, relative=False):
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
    return out[EXPORT_COLUMNS]


def compare_multiple_groups(rows, groups):
    """Compare disjoint groups using relative landmarks and unchanged kinetics.

    `groups` maps display names to collections of stable File IDs.
    """
    groups = {str(name): list(ids) for name, ids in groups.items()}
    if len(groups) < 2 or any(not ids for ids in groups.values()):
        raise ValueError('Assign at least one file to each of two or more groups.')
    flattened = [file_id for ids in groups.values() for file_id in ids]
    if len(flattened) != len(set(flattened)):
        raise ValueError('A recording can only be assigned to one group.')
    indexed = results_frame(rows).set_index('File ID', drop=False)
    if not set(flattened) <= set(indexed.index):
        raise ValueError('Group assignments must come from the current analysis.')
    rel = export_frame(rows, relative=True)
    rel.index = indexed.index
    figures, summary = [], []
    for measure in COMPARISON_COLUMNS:
        fig = go.Figure()
        subtitle = []
        for n, (name, ids) in enumerate(groups.items()):
            numeric = pd.to_numeric(rel.loc[ids, measure], errors='coerce')
            valid = numeric[np.isfinite(numeric)]
            subtitle.append(f'{name} n={len(valid)}')
            color = GROUP_COLORS[n % len(GROUP_COLORS)]
            fig.add_trace(go.Box(y=valid.tolist(), name=name, boxpoints=False,
                                 line=dict(color=color), fillcolor=color, opacity=.65))
            summary.append({
                'Measure': measure, 'Group': name, 'n': len(valid),
                'Missing': len(ids) - len(valid),
                'Mean': valid.mean(), 'Median': valid.median(),
                'SD': valid.std(ddof=1),
            })
        fig.update_layout(title=f"{measure}<br><sup>{' · '.join(subtitle)}</sup>",
                          yaxis_title=measure, template='plotly_white', height=360,
                          margin=dict(l=20, r=20, t=70, b=45))
        figures.append(fig)
    return figures, pd.DataFrame(summary)


def compare_groups(rows, group1, group2):
    """Backward-compatible two-group interface, now using relative timestamps."""
    return compare_multiple_groups(rows, {'Group 1': group1, 'Group 2': group2})
