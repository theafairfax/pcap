"""One first-AP/AHP pair per sweep, using a versioned measurement definition."""
from dataclasses import dataclass, asdict
import numpy as np
from .measurements import analyze_events, detect_peaks

ANALYSIS_VERSION = 'first-event-1.3'
LEGACY_ANALYSIS_VERSION = 'first-event-1.0'
MARKERS = ('Location', 'Onset', 'Rise 10%', 'Rise 90%', 'Half rise', 'Half fall', 'Rebound')


@dataclass(frozen=True)
class Settings:
    height: float = -10.
    prominence: float = 20.
    separation_ms: float = 2.
    dvdt_threshold: float = 20.
    ahp_window_ms: float = 50.
    ahp_trough_window_ms: float = 3.
    ahp_post_injection: bool = False
    start_ms: float | None = None
    end_ms: float | None = None


def injection_window(sweep, settings):
    t = sweep.time
    lo, hi = float(t[0]), float(t[-1])
    source = 'Full sweep (no resolvable current step)'
    current = sweep.current
    if current is not None and np.all(np.isfinite(current)):
        base = np.median(current[:max(2, int(.02*len(current)))])
        dev = np.abs(current-base)
        if dev.max() > 1.:
            active = np.flatnonzero(dev > max(1., .05*dev.max()))
            lo, hi = float(t[active[0]]), float(t[min(active[-1]+1, len(t)-1)])
            source = 'Current-derived injection window'
    if settings.start_ms is not None:
        lo = settings.start_ms/1000.
        source = 'User-defined injection window'
    if settings.end_ms is not None:
        hi = settings.end_ms/1000.
        source = 'User-defined injection window'
    if not t[0] <= lo < hi <= t[-1]:
        raise ValueError('Injection window must lie inside the sweep, with start before end.')
    return lo, hi, source


def count_spikes(sweep, settings):
    lo, hi, _ = injection_window(sweep, settings)
    peaks = detect_peaks(sweep.time, sweep.voltage, settings.height, settings.prominence, settings.separation_ms)
    return int(np.sum((sweep.time[peaks] >= lo) & (sweep.time[peaks] < hi)))


def first_event(sweep, settings=Settings(), metadata=None):
    lo, hi, source = injection_window(sweep, settings)
    kwargs = asdict(settings)
    kwargs.pop('start_ms'); kwargs.pop('end_ms')
    rows = analyze_events(sweep.time, sweep.voltage, lo, hi, **kwargs)
    if not rows:
        raise ValueError('No AP detected in this sweep’s injection window. Choose another sweep or adjust analysis.')
    row = rows[0]
    # Include a little pre-onset context but no second AP in the stored capture.
    peak = row['SPIKE Location (ms)']
    start = row.get('_Event start (ms)', max(sweep.time[0]*1000, peak-5.))
    end = row.get('_Event end (ms)', min(hi*1000, peak+settings.ahp_window_ms))
    mask = (sweep.time*1000 >= start) & (sweep.time*1000 <= end)
    return {'schema_version': 1, 'analysis_version': ANALYSIS_VERSION,
            'metadata': dict(metadata or {}, sweep=int(sweep.index), window_source=source,
                             injection_start_ms=lo*1000, injection_end_ms=hi*1000),
            'settings': asdict(settings), 'time_ms': sweep.time[mask]*1000,
            'voltage_mv': sweep.voltage[mask], 'measurements': row}


def metrics(event, block):
    r = event['measurements']
    onset = r.get(f'{block} Onset (ms)', np.nan)
    peak = r.get(f'{block} Location (ms)', np.nan)
    origin = r['SPIKE Location (ms)']
    return {
        'Peak Vm (mV)' if block == 'SPIKE' else 'Trough Vm (mV)': r[f'{block} Peak Membrane Voltage-1 (mV)'],
        'Amplitude from AP threshold (mV)': r['AP amplitude (mV)' if block == 'SPIKE' else 'AHP amplitude from threshold (mV)'],
        'Onset relative to event location (ms)': onset-peak,
        'Rise 10–90% (ms)': r[f'{block} Rise (ms)'],
        'Half-height width (ms)': r[f'{block} Width (ms)'],
        **({'AP peak to trough (ms)': peak-origin,\n            'AHP onset time (ms)': onset, 'AHP trough time (ms)': peak,\n            'AHP trough voltage (mV)': r['AHP trough Vm (mV)'],\n            'AHP half-fall time (ms)': r.get('AHP Half fall (ms)', np.nan),\n            'AHP rebound time (ms)': r.get('AHP Rebound (ms)', np.nan),\n            'AHP rebound latency from trough (ms)': r.get('AHP Rebound latency (ms)', np.nan)} if block == 'AHP' else {})}


def alignment(event, block, mode):
    r = event['measurements']
    key = 'SPIKE Location (ms)' if mode == 'AP peak' else f'{block} '+('Onset (ms)' if mode == 'Event onset' else 'Location (ms)')
    origin = r.get(key, np.nan)
    if not np.isfinite(origin):
        raise ValueError(f'{block} {mode.lower()} alignment is unresolved.')
    return float(origin)


def coordinates(event, block, mode, normalize):
    r = event['measurements']
    t, v = np.asarray(event['time_ms']), np.asarray(event['voltage_mv'])
    origin = alignment(event, block, mode)
    onset = r.get('SPIKE Onset (ms)', np.nan)
    half_fall = r.get('SPIKE Half fall (ms)', np.nan)
    if not np.isfinite(onset) or not np.isfinite(half_fall):
        raise ValueError('Waveform display requires resolved AP onset and half-fall.')
    lo, hi = max(t[0], onset-2.), min(t[-1], half_fall+3.)
    if hi <= lo:
        raise ValueError('No captured samples in the waveform display window.')
    # Interpolate at the exact display boundaries, preserving all interior samples.
    visible_t = np.concatenate(([lo], t[(t > lo) & (t < hi)], [hi]))
    visible_v = np.interp(visible_t, t, v)
    base, scale = 0., 1.
    if normalize:
        base = r.get('Threshold Vm (mV)', np.nan)
        amplitude = r.get('AP amplitude (mV)' if block == 'SPIKE' else 'AHP amplitude from threshold (mV)', np.nan)
        if not np.isfinite(base) or not np.isfinite(amplitude) or abs(amplitude) < 1e-9:
            raise ValueError(f'{block} normalization requires resolved threshold and amplitude.')
        scale = abs(amplitude)
    return visible_t-origin, (visible_v-base)/scale, origin, base, scale
