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
                   + ['AP peak to AHP trough (ms)', 'AHP onset time (ms)', 'AHP trough time (ms)',\n                      'AHP trough voltage (mV)', 'AHP half-fall time (ms)',\n                      'AHP rebound time (ms)', 'AHP rebound latency from trough (ms)'])
MARKER_COLUMNS = [f'{block} {marker} (ms)' for block in ('AP','AHP') for marker in MARKERS]
COLUMNS = (['File ID','Filename','Status','Detail','Sweep','APs in selected sweep','Analysis version',
            'Voltage channel rank','Analysis settings','Injection start (ms)','Injection end (ms)',
            'Injection window source','AP threshold Vm (mV)'] + KINETIC_COLUMNS + MARKER_COLUMNS)


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
        row.update({'Sweep': selected.index, 'APs in selected sweep': count,
                    'Injection start (ms)': meta['injection_start_ms'],
                    'Injection end (ms)': meta['injection_end_ms'],
                    'Injection window source': meta['window_source'],
                    'AP threshold Vm (mV)': r['Threshold Vm (mV)']})
        for block, label in (('SPIKE','AP'), ('AHP','AHP')):
            for name, value in metrics(event, block).items():
                if name.startswith('AHP ') and name in KINETIC_COLUMNS:\n                    row[name] = value\n                elif name == 'AP peak to trough (ms)':
                    row['AP peak to AHP trough (ms)'] = value
                elif name == 'Half-height width (ms)':
                    # Explicitly use the two half-height crossings for both events.
                    row[f'{label} Half width (ms)'] = r.get(f'{block} Half fall (ms)',np.nan)-r.get(f'{block} Half rise (ms)',np.nan)
                else:
                    row[f'{label} {name}'] = value
            for marker in MARKERS:
                row[f'{label} {marker} (ms)'] = r.get(f'{block} {marker} (ms)', np.nan)
        required = [c for c in KINETIC_COLUMNS if 'rebound' not in c.lower()]\n        row['Status'] = 'OK' if all(np.isfinite(row[c]) for c in required) else 'Partial'
        row['Detail'] = r['Status']
    except Exception as err:
        row.update(Status='Error', Detail=str(err))
    return row


def results_frame(rows):
    return pd.DataFrame(rows, columns=COLUMNS)


def compare_groups(rows, group1, group2):
    """One file is one observation; omit missing values independently per measure."""
    if not group1 or not group2:
        raise ValueError('Select at least one file in each group.')
    if set(group1) & set(group2):
        raise ValueError('A file cannot belong to both groups.')
    frame = results_frame(rows).set_index('File ID', drop=False)
    if not (set(group1) | set(group2)) <= set(frame.index):
        raise ValueError('Group selections must belong to the current batch.')
    figures, summary = [], []
    for measure in KINETIC_COLUMNS:
        fig = go.Figure()
        counts = []
        for ids, name, color in ((group1,'Group 1','#475569'),(group2,'Group 2','#dc645b')):
            values = pd.to_numeric(frame.loc[list(ids), measure], errors='coerce')
            values = values[np.isfinite(values)]
            counts.append(len(values))
            fig.add_trace(go.Box(y=values.tolist(), name=name, boxpoints=False,
                                 line=dict(color=color), fillcolor=color, opacity=.65))
            summary.append({'Measure': measure, 'Group': name, 'n': len(values),
                            'Missing': len(ids)-len(values),
                            'Mean': values.mean(), 'Median': values.median(),
                            'SD': values.std(ddof=1)})
        fig.update_layout(title=f'{measure}<br><sup>Group 1 n={counts[0]} · Group 2 n={counts[1]}</sup>',
                          yaxis_title=measure, template='plotly_white', height=340,
                          showlegend=False, margin=dict(l=20,r=20,t=70,b=30))
        figures.append(fig)
    return figures, pd.DataFrame(summary)
