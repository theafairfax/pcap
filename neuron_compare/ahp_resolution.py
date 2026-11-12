"""Descriptive AHP-trough detection counts and categorical group comparison.

A 'resolved AHP' means an AHP trough was identified after a detected AP;
a later half-recovery crossing is not required. The denominator includes only
analyzed recordings with a detected AP. No-AP and read-error files are excluded.
"""
import numpy as np
import pandas as pd
import plotly.graph_objects as go
from scipy.stats import chi2_contingency, fisher_exact

from .bulk import results_frame


def ahp_resolution_analysis(rows, groups):
    """Return a percent-stacked bar plot, group counts and omnibus test table.

    One recording is one observation. This is *not* valid for repeated files
    from the same neuron/animal without appropriate clustered analysis.
    """
    indexed = results_frame(rows).set_index('File ID', drop=False)
    records = []
    for name, ids in groups.items():
        cohort = indexed.loc[list(ids)]
        ap = pd.to_numeric(cohort['AP Location (ms)'], errors='coerce')
        eligible = cohort.loc[ap.notna() & cohort['Status'].isin(('OK', 'Partial'))]
        trough = pd.to_numeric(eligible['AHP Location (ms)'], errors='coerce')
        depth = pd.to_numeric(eligible['AHP Amplitude from AP threshold (mV)'], errors='coerce')
        # Legacy 16-column files still contain these two measures. Missing
        # absolute Vm must not cause a resolved trough to be counted as missing.
        resolved = trough.notna() & depth.notna() & (depth < 0)
        yes = int(resolved.sum())
        no = int(len(eligible) - yes)
        records.append({
            'Group': name, 'Resolved': yes, 'Unresolved': no,
            'AP-positive n': len(eligible),
            'Excluded (no valid AP)': len(cohort) - len(eligible),
            'Resolved (%)': 100. * yes / len(eligible) if len(eligible) else np.nan,
        })
    counts = pd.DataFrame(records)
    matrix = counts[['Resolved', 'Unresolved']].to_numpy(dtype=int)
    chi2, p, dof, min_expected, fisher_p = (np.nan, np.nan, np.nan, np.nan, np.nan)
    note = ''
    if np.any(matrix.sum(axis=1) == 0):
        note = 'At least one group has no eligible AP-positive recordings.'
    elif np.any(matrix.sum(axis=0) == 0):
        note = 'Only one outcome observed; chi-squared test is undefined.'
    else:
        chi2, p, dof, expected = chi2_contingency(matrix, correction=False)
        min_expected = float(np.min(expected))
        if min_expected < 5:
            note = ('At least one expected count is below 5; Pearson chi-squared '
                    'approximation may be unreliable.')
            if len(groups) == 2:
                fisher_p = float(fisher_exact(matrix).pvalue)
    statistics = pd.DataFrame([{
        'Test': 'Pearson chi-squared (all groups)',
        'Chi-squared': chi2, 'df': dof, 'p-value': p,
        'Minimum expected cell count': min_expected,
        'Fisher exact p-value (2 groups)': fisher_p,
        'Note': note or 'Expected counts at least 5.',
    }])
    fig = go.Figure()
    for key, color in (('Resolved', '#16a085'), ('Unresolved', '#d97757')):
        heights = [100. * row[key] / row['AP-positive n']
                   if row['AP-positive n'] else 0. for _, row in counts.iterrows()]
        fig.add_trace(go.Bar(
            x=counts['Group'].tolist(), y=heights, name=key,
            marker_color=color,
            text=[f"{int(row[key])}/{int(row['AP-positive n'])}"
                  if row['AP-positive n'] and row[key] else ''
                  for _, row in counts.iterrows()],
            textposition='inside',
            hovertemplate='%{x}<br>'+key+': %{y:.1f}%<extra></extra>',
        ))
    report = ('Pearson χ² p=' + (f'{p:.4g}' if np.isfinite(p) else 'N/A'))
    if np.isfinite(fisher_p):
        report += f' · Fisher exact p={fisher_p:.4g}'
    fig.update_layout(
        title='AHP trough identification by group',
        barmode='stack', template='plotly_white', height=450,
        yaxis=dict(title='AP-positive recordings (%)', range=[0, 105]),
        xaxis_title='Experimental group',
        legend=dict(orientation='h', y=1.10),
        margin=dict(l=30, r=20, t=95, b=100),
        meta={'test': report, 'note': note},
    )
    fig.add_annotation(x=.5, y=-.20, xref='paper', yref='paper',
                       text=report, showarrow=False, font=dict(size=11))
    return fig, counts, statistics
