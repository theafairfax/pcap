"""Black query, gray reference, and matching colored measurement intersections."""
import numpy as np
import plotly.graph_objects as go
from .core import MARKERS, alignment

COLORS = ('#e05252', '#9063cf', '#039eb7', '#13a475', '#d88e20', '#d359a0')


def coordinates(event, block, mode, normalize):
    r = event['measurements']
    t, v = np.asarray(event['time_ms']), np.asarray(event['voltage_mv'])
    origin = alignment(event, block, mode)
    peak = r['SPIKE Location (ms)']
    if block == 'SPIKE':
        end = r.get('AHP Onset (ms)', np.nan)
        end = min(end, peak+5.) if np.isfinite(end) else peak+5.
        mask = (t >= peak-5.) & (t <= end)
    else:
        onset = r.get('AHP Onset (ms)', np.nan)
        mask = t >= (onset if np.isfinite(onset) else peak+.5)
    base, scale = 0., 1.
    if normalize:
        base = r.get('Threshold Vm (mV)', np.nan)
        amplitude = r.get('AP amplitude (mV)' if block == 'SPIKE' else 'AHP amplitude from threshold (mV)', np.nan)
        if not np.isfinite(base) or not np.isfinite(amplitude) or abs(amplitude) < 1e-9:
            raise ValueError(f'{block} normalization requires resolved threshold and amplitude.')
        scale = abs(amplitude)
    return t[mask]-origin, (v[mask]-base)/scale, origin, base, scale


def overlay(query, reference, cohort, block='SPIKE', mode='Event location', normalize=False, highlight='All markers'):
    fig = go.Figure()
    ranges = []
    for event in [query]+list(cohort):
        try:
            x,y,*_ = coordinates(event,block,mode,normalize)
            if len(x):
                ranges.append((x.min(),x.max(),y.min(),y.max()))
        except ValueError:
            continue
    # Reference first, so the black query and its markers stay on top.
    for event, name, color, opacity in ((reference,'Reference','#a9b0bb',.45), (query,'Your neuron','#111827',1.)):
        if event is None:
            continue
        try:
            x,y,origin,base,scale = coordinates(event,block,mode,normalize)
        except ValueError:
            continue
        if not len(x):
            continue
        fig.add_trace(go.Scatter(x=x,y=y,mode='lines',name=name,line=dict(color=color,width=2.5 if name=='Your neuron' else 2),
                                 hovertemplate=name+'<br>%{x:.4f} ms<br>%{y:.4f}<extra></extra>'))
        r = event['measurements']
        for marker,c in zip(MARKERS,COLORS):
            if highlight != 'All markers' and marker != highlight:
                continue
            value = r.get(f'{block} {marker} (ms)',np.nan)
            if not np.isfinite(value):
                continue
            mv = (np.interp(value,event['time_ms'],event['voltage_mv'])-base)/scale
            fig.add_vline(x=value-origin,line_color=c,opacity=opacity,line_width=1.2,
                          line_dash='solid' if name=='Your neuron' else 'dash')
            fig.add_trace(go.Scatter(x=[value-origin],y=[mv],mode='markers',name=name+' · '+marker,
                                     marker=dict(color=c,size=7,opacity=opacity),showlegend=False,
                                     hovertemplate=name+' · '+marker+'<br>%{x:.4f} ms<extra></extra>'))
    fig.update_layout(template='plotly_white',height=440,margin=dict(l=20,r=20,t=25,b=30),
                      xaxis_title=f'Time from {mode.lower()} (ms)',
                      yaxis_title='Amplitude / event magnitude' if normalize else 'Membrane potential (mV)',
                      legend=dict(orientation='h',y=1.1),hovermode='closest')
    if ranges:
        a=np.asarray(ranges)
        xmin,xmax,ymin,ymax=a[:,0].min(),a[:,1].max(),a[:,2].min(),a[:,3].max()
        pad=max((ymax-ymin)*.08,.05 if normalize else 1.)
        fig.update_xaxes(range=[xmin,xmax])
        fig.update_yaxes(range=[ymin-pad,ymax+pad])
    return fig
