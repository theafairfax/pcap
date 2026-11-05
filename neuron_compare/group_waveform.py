"""Landmark-derived schematic AP/AHP profiles (not averaged voltage traces).

The 16-column bulk export carries times and amplitudes but no absolute voltages
or raw samples. Therefore profiles show mV relative to AP threshold (0 mV).
Each landmark coordinate is the mean of that measurement across cells; PCHIP
joins them visually but adds no independent observations.
"""
import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from scipy.interpolate import PchipInterpolator
from .bulk import export_frame, results_frame, GROUP_COLORS, SIGNIFICANCE_METHODS, significance_label

# Timestamp column, height as fraction of mean AP amplitude or AHP depth.
LANDMARKS = (
    ('AP Onset (ms)', 0., 'AP onset'),
    ('AP Rise 10% (ms)', .1, 'Rise 10%'),
    ('AP Half rise (ms)', .5, 'Half rise'),
    ('AP Rise 90% (ms)', .9, 'Rise 90%'),
    ('AP Location (ms)', 1., 'AP peak'),
    ('AP Half fall (ms)', .5, 'Half fall'),
    ('AHP Onset (ms)', 0., 'AHP onset'),
    ('AHP Half-Fall (ms)', -.5, 'AHP half-fall'),
    ('AHP Location (ms)', -1., 'AHP trough'),
)
# Independent hypotheses already included in the comparison family.
TEST_MEASURES = {
    'AP onset':'AP Onset (ms)', 'Rise 10%':'AP Rise 10% (ms)',
    'Half rise':'AP Half rise (ms)', 'Rise 90%':'AP Rise 90% (ms)',
    'Half fall':'AP Half fall (ms)', 'AHP onset':'AHP Onset (ms)',
    'AHP half-fall':'AHP Half-Fall (ms)', 'AHP trough':'AHP Location (ms)',
    'AP peak':'AP amplitude (mV)', 'AHP depth':'AHP amplitude (mV)',
}

def significant_waveform_pairs(tests, groups, significance_method='Holm-Bonferroni'):
    """Return significant group/landmark tests, using the boxplots' corrected family.

    These results describe measured landmarks, not comparisons between fitted
    curve samples. Keep full group labels to disambiguate 3–6 group overlays.
    """
    if significance_method not in SIGNIFICANCE_METHODS:
        raise ValueError('Unknown significance method.')
    column = SIGNIFICANCE_METHODS[significance_method]
    relevant = {measure: label for label, measure in TEST_MEASURES.items()}
    names = set(groups)
    out = []
    for _, result in tests.iterrows():
        metric = result['Measure']
        a, b = result['Group A'], result['Group B']
        if metric not in relevant or a not in names or b not in names:
            continue
        p = float(result[column])
        if not np.isfinite(p) or p >= .05:
            continue
        out.append({
            'Landmark': relevant[metric],
            'Group A': a, 'Group B': b,
            'Significance': significance_label(p),
            'Adjusted p-value': p,
        })
    return sorted(out, key=lambda r: (
        list(TEST_MEASURES).index(r['Landmark']),
        list(groups).index(r['Group A']), list(groups).index(r['Group B'])
    ))


def group_landmarks(rows, groups):
    frame = export_frame(rows, relative=True)
    frame.index = results_frame(rows)['File ID'].astype(str)
    data = {}
    for name, ids in groups.items():
        cohort = frame.loc[list(ids)]
        ap = pd.to_numeric(cohort['AP amplitude (mV)'], errors='coerce').mean()
        ahp = pd.to_numeric(cohort['AHP amplitude (mV)'], errors='coerce').mean()
        if not np.isfinite(ap) or not np.isfinite(ahp) or ap <= 0 or ahp <= 0:
            continue
        points = []
        for column, factor, label in LANDMARKS:
            x = pd.to_numeric(cohort[column], errors='coerce').mean()
            if np.isfinite(x):
                points.append((float(x), float(factor*(ap if factor >= 0 else ahp)), label))
        # Keep chronological order. Coincident markers share one x; avoid
        # manufacturing an interpolation crossing across duplicate timestamps.
        points.sort(key=lambda item: item[0])
        unique = []
        for point in points:
            if unique and abs(unique[-1][0] - point[0]) < 1e-8:
                continue
            unique.append(point)
        if len(unique) >= 3:
            data[name] = unique
    return data


def prototype_figure(rows, groups, tests, significance_method='Holm-Bonferroni'):
    """Overlay up to six mean-landmark profiles and annotate two-group differences.

    Time and voltage marker tests are reused from the *same* corrected family
    as the boxplots. No p-values are calculated from the schematic lines.
    """
    if significance_method not in SIGNIFICANCE_METHODS:
        raise ValueError('Unknown significance method.')
    profiles = group_landmarks(rows, groups)
    # More than two waveforms need a group-pair key INSIDE the downloadable
    # graphic, not unexplained stars near densely overlapping curves.
    pair_rows = significant_waveform_pairs(
        tests, groups, significance_method) if len(groups) > 2 else []
    multi = len(groups) > 2
    table_height = max(150, (len(pair_rows) + 1) * 25) if multi else 0
    chart_height = 515
    if multi:
        total_height = chart_height + table_height + 70
        fig = make_subplots(
            rows=2, cols=1, specs=[[{'type': 'xy'}], [{'type': 'table'}]],
            row_heights=[chart_height, table_height],
            vertical_spacing=min(.06, 40 / total_height))
    else:
        fig = go.Figure()
    point_lookup = {}
    def add_curve(trace):
        if multi:
            fig.add_trace(trace, row=1, col=1)
        else:
            fig.add_trace(trace)
    for i, (name, points) in enumerate(profiles.items()):
        x = np.asarray([p[0] for p in points])
        y = np.asarray([p[1] for p in points])
        color = GROUP_COLORS[i % len(GROUP_COLORS)]
        smooth_x = np.linspace(x[0], x[-1], 500)
        smooth_y = PchipInterpolator(x, y)(smooth_x)
        add_curve(go.Scatter(x=smooth_x, y=smooth_y, mode='lines', name=name,
                                 line=dict(color=color, width=3),
                                 hovertemplate=name+'<br>t=%{x:.3f} ms<br>relative Vm=%{y:.2f} mV<extra></extra>'))
        add_curve(go.Scatter(x=x, y=y, mode='markers', name=name+' landmarks',
                                 marker=dict(color=color, size=9, line=dict(color='white',width=1)),
                                 text=[p[2] for p in points],
                                 customdata=np.array([[len(groups[name])]]*len(points)),
                                 hovertemplate='%{text}<br>t=%{x:.3f} ms<br>relative Vm=%{y:.2f} mV<extra></extra>',
                                 showlegend=False))
        point_lookup[name] = {p[2]: p for p in points}
    # Significance stars use the specified p-value adjustment. They live
    # adjacent to the landmark tested, not between arbitrary curve samples.
    if len(groups) == 2 and len(profiles) == 2:
        group_names = list(groups)
        column = SIGNIFICANCE_METHODS[significance_method]
        finite_y = [p[1] for v in profiles.values() for p in v]
        pad = max(3., (max(finite_y)-min(finite_y))*.08) if finite_y else 4.
        for label, measure in TEST_MEASURES.items():
            match = tests.loc[tests['Measure'].eq(measure) &
                              tests['Group A'].eq(group_names[0]) &
                              tests['Group B'].eq(group_names[1])]
            point_label = 'AHP trough' if label == 'AHP depth' else label
            if match.empty or point_label not in point_lookup[group_names[0]] or point_label not in point_lookup[group_names[1]]:
                continue
            p = float(match.iloc[0][column])
            if not np.isfinite(p) or p >= .05:
                continue
            a, b = point_lookup[group_names[0]][point_label], point_lookup[group_names[1]][point_label]
            # Horizontal timing offset or vertical voltage difference.
            is_voltage = measure.endswith('amplitude (mV)')
            xx = (a[0]+b[0])/2
            yy = max(a[1],b[1])+pad*(1.1 if label == 'AP peak' else (-.7 if label == 'AHP depth' else .45))
            fig.add_annotation(x=xx,y=yy,text=significance_label(p),
                               showarrow=False,font=dict(size=15,color='#111827'),
                               hovertext=f'{label}: {significance_method}; p={p:.4g}')
    if multi:
        if pair_rows:
            columns = [
                [r['Landmark'] for r in pair_rows],
                [r['Group A'] + ' vs ' + r['Group B'] for r in pair_rows],
                [r['Significance'] for r in pair_rows],
                [f"{r['Adjusted p-value']:.4g}" for r in pair_rows],
            ]
        else:
            columns = [['No significant landmark differences'], ['—'], ['—'], ['—']]
        fig.add_trace(go.Table(
            header=dict(values=['Landmark', 'Compared groups', 'Significance',
                                significance_method + ' p'],
                        fill_color='#e2e8f0', align='left', height=26,
                        font=dict(size=11, color='#334155')),
            cells=dict(values=columns, align='left', height=25,
                       fill_color='#f8fafc', font=dict(size=10)),
            columnwidth=[130, 175, 85, 160]), row=2, col=1)
    if multi:
        # Plotly's add_vline/add_hline helpers cannot be used on figures
        # containing a Table subplot; add shapes directly to the XY axes.
        fig.add_shape(type='line', xref='x', yref='y domain',
                      x0=0, x1=0, y0=0, y1=1,
                      line=dict(color='#94a3b8', dash='dash', width=1))
        fig.add_shape(type='line', xref='x domain', yref='y',
                      x0=0, x1=1, y0=0, y1=0,
                      line=dict(color='#94a3b8', dash='dot', width=1))
    else:
        fig.add_vline(x=0, line=dict(color='#94a3b8', dash='dash', width=1))
        fig.add_hline(y=0, line=dict(color='#94a3b8', dash='dot', width=1))
    fig.update_layout(title='Prototypical AP/AHP by group · mean kinetic landmarks',
                      template='plotly_white',height=(chart_height + table_height + 70 if multi else 530),
                      margin=dict(l=55,r=30,t=65,b=95),
                      xaxis_title='Time relative to AP peak (ms)',
                      yaxis_title='Membrane potential relative to AP threshold (mV)',
                      legend=dict(orientation='h',y=1.08 if not multi else 1.02),
                      annotations=list(fig.layout.annotations or []))
    return fig
