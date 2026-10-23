"""Safe, portable JSON reference records; no pickle or executable uploads."""
import json
from pathlib import Path
import numpy as np
from .core import ANALYSIS_VERSION, LEGACY_ANALYSIS_VERSION
from .measurements import analyze_events


def clean(value):
    if isinstance(value, np.ndarray):
        return clean(value.tolist())
    if isinstance(value, dict):
        return {k: clean(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [clean(v) for v in value]
    if isinstance(value, (float, np.floating)):
        return float(value) if np.isfinite(value) else None
    if isinstance(value, np.integer):
        return int(value)
    return value


def save_collection(path, events):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps({'schema_version': 1, 'events': clean(events)}, indent=2, allow_nan=False))


def load_collection(path):
    return parse_collection(json.loads(Path(path).read_text()))


def parse_collection(data):
    if data.get('schema_version') != 1:
        raise ValueError('Unsupported reference schema.')
    events = data.get('events', [])
    ids = set()
    for event in events:
        if event.get('analysis_version') not in (ANALYSIS_VERSION, LEGACY_ANALYSIS_VERSION):
            raise ValueError('Reference measurements use a different analysis version; regenerate the collection.')
        event['time_ms'] = np.asarray(event['time_ms'], dtype=float)
        event['voltage_mv'] = np.asarray(event['voltage_mv'], dtype=float)
        t, v = event['time_ms'], event['voltage_mv']
        if t.ndim != 1 or v.shape != t.shape or len(t) < 3 or not np.all(np.isfinite(t)) or not np.all(np.isfinite(v)) or not np.all(np.diff(t) > 0):
            raise ValueError('Reference waveform must contain finite, increasing time and matching voltage.')
        event['measurements'] = {k: np.nan if value is None else value for k,value in event['measurements'].items()}
        if event['analysis_version'] == LEGACY_ANALYSIS_VERSION:
            # Legacy captures retain the AP and recovery samples needed for the new cutoff.
            settings = dict(event['settings'])
            settings.pop('start_ms', None); settings.pop('end_ms', None)
            meta = event['metadata']
            lo = max(t[0]/1000., meta.get('injection_start_ms', t[0])/1000.)
            hi = min(t[-1]/1000., meta.get('injection_end_ms', t[-1])/1000.)
            rows = analyze_events(t/1000., v, lo, hi, **settings)
            if not rows:
                raise ValueError('Legacy reference has no detectable AP; regenerate the collection.')
            event['measurements'] = rows[0]
            event['analysis_version'] = ANALYSIS_VERSION

        uid = event['metadata']['id']
        if uid in ids:
            raise ValueError('Duplicate reference ID: '+str(uid))
        ids.add(uid)
    return events
