"""Read current-clamp recordings. Voltage is mV, current pA, time seconds."""
from dataclasses import dataclass
from pathlib import Path
import tempfile
import numpy as np


@dataclass
class Sweep:
    index: int
    time: np.ndarray
    voltage: np.ndarray
    current: np.ndarray | None = None


def _validate(sweeps):
    if not sweeps:
        raise ValueError('No voltage sweeps found. Upload a current-clamp recording.')
    for s in sweeps:
        if len(s.time) < 3 or len(s.time) != len(s.voltage):
            raise ValueError('A sweep has missing or mismatched voltage samples.')
        if not np.all(np.isfinite(s.voltage)) or not np.all(np.diff(s.time) > 0):
            raise ValueError('Voltage must be finite and sweep time must increase.')
        if s.current is not None and len(s.current) != len(s.time):
            s.current = None
    return sweeps


def load_recording(data, filename, voltage_channel=0):
    """voltage_channel is a zero-based rank among voltage channels, not ADC ID."""
    suffix = Path(filename).suffix.lower()
    if suffix not in ('.abf', '.axgd', '.axgx'):
        raise ValueError('Choose an ABF, AXGD or AXGX file.')
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / ('recording'+suffix)
        path.write_bytes(data)
        sweeps = _abf(path, voltage_channel) if suffix == '.abf' else _axograph(path, voltage_channel)
    return _validate(sweeps)


def _abf(path, channel):
    import pyabf
    abf = pyabf.ABF(str(path))
    scales = {'v': 1000., 'mv': 1., 'uv': .001, 'µv': .001, 'μv': .001}
    channels = [i for i, unit in enumerate(abf.adcUnits) if unit.strip().lower() in scales]
    if not 0 <= channel < len(channels):
        raise ValueError(f'Voltage channel rank must be below {len(channels)}.')
    selected = channels[channel]
    out = []
    for idx in abf.sweepList:
        abf.setSweep(idx, channel=selected)
        current = None
        # Use only an actual current ADC, or a command explicitly expressed in current units.
        cscales = {'a': 1e12, 'na': 1000., 'pa': 1.}
        current_adc = next((i for i,u in enumerate(abf.adcUnits) if u.lower().strip() in cscales), None)
        t = np.asarray(abf.sweepX, dtype=float).copy()
        v = np.asarray(abf.sweepY, dtype=float).copy()*scales[abf.adcUnits[selected].strip().lower()]
        command_unit = str(abf.sweepUnitsC).strip().lower()
        if command_unit in cscales:
            current = np.asarray(abf.sweepC, dtype=float).copy()*cscales[command_unit]
        if current_adc is not None:
            abf.setSweep(idx, channel=current_adc)
            current = np.asarray(abf.sweepY, dtype=float).copy()*cscales[abf.adcUnits[current_adc].lower().strip()]
        out.append(Sweep(int(idx), t-t[0], v, current))
    return out


def _axograph(path, channel):
    from neo.io import AxographIO
    import quantities as pq
    block = AxographIO(str(path)).read_block()
    out = []
    for idx, segment in enumerate(block.segments):
        voltages, currents = [], []
        for signal in segment.analogsignals:
            # Unit-based selection prevents current-only recordings being called voltage.
            try:
                values = signal.rescale(pq.mV).magnitude
                voltages.extend((signal, values[:, j]) for j in range(values.shape[1]))
                continue
            except ValueError:
                pass
            try:
                values = signal.rescale(pq.pA).magnitude
                currents.extend((signal, values[:, j]) for j in range(values.shape[1]))
            except ValueError:
                pass
        if not 0 <= channel < len(voltages):
            raise ValueError(f'Sweep {idx}: found {len(voltages)} voltage channels; check channel rank.')
        signal, voltage = voltages[channel]
        t = np.asarray(signal.times.rescale(pq.s).magnitude, dtype=float).flatten()
        current = None
        if currents:
            csig, cv = currents[0]
            ct = np.asarray(csig.times.rescale(pq.s).magnitude).flatten()
            if len(ct) == len(t) and np.allclose(ct, t, rtol=0, atol=1e-9):
                current = np.asarray(cv, dtype=float).copy()
        out.append(Sweep(idx, t-t[0], np.asarray(voltage, dtype=float).copy(), current))
    return out
