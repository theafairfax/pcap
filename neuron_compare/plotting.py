"""Black query, gray reference, and matching colored measurement intersections."""
import numpy as np
import plotly.graph_objects as go
from .core import MARKERS, coordinates

COLORS = ('#e05252', '#9063cf', '#039eb7', '#13a475', '#d88e20', '#d359a0')


def overlay(query, reference, cohort, block='SPIKE', mode='Event location', normalize=False, highlight='All markers', range_bounds=None):
    fig = go.Figure()
    # Legacy cohort bounds describe longer captures; fit only the visible pair.
    ranges = []
    for event in [query,reference]:
        if event is None:
            continue
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
            if not np.isfinite(value) or not x[0] <= value-origin <= x[-1]:
                continue
            mv = (np.interp(value,event['time_ms'],event['voltage_mv'])-base)/scale
            fig.add_vline(x=value-origin,line_color=c,opacity=opacity,line_width=1.2,
                          line_dash='solid' if name=='Your neuron' else 'dash')
            fig.add_trace(go.Scatter(x=[value-origin],y=[mv],mode='markers',name=name+' · '+marker,
                                     marker=dict(color=c,size=7,opacity=opacity),showlegend=False,
                                     hovertemplate=name+' · '+marker+'<br>%{x:.4f} ms<extra></extra>'))
    fig.update_layout(template='plotly_white',height=440,margin=dict(l=20,r=20,t=25,b=30),
                      xaxis_title=f"Time from {('AP peak' if block=='SPIKE' else 'AHP trough') if mode=='Event location' else mode.lower()} (ms)",
                      yaxis_title='Amplitude / event magnitude' if normalize else 'Membrane potential (mV)',
                      legend=dict(orientation='h',y=1.1),hovermode='closest')
    if ranges:
        a=np.asarray(ranges)
        xmin,xmax,ymin,ymax=a[:,0].min(),a[:,1].max(),a[:,2].min(),a[:,3].max()
        pad=max((ymax-ymin)*.08,.05 if normalize else 1.)
        fig.update_xaxes(range=[xmin,xmax],zeroline=True,zerolinecolor='#cbd5e1',tick0=0)
        fig.update_yaxes(range=[ymin-pad,ymax+pad])
    return fig
