"""AP/AHP measurements; times are sweep-relative ms.

Adapted from theafairfax/axgd_analyzer, commit 4ea866a (abf_analysis.py).
See README for definitions and provenance.
"""
import numpy as np
from scipy.signal import find_peaks


def crossing(t, v, level, start, stop, rising):
    for j in range(max(0, start), min(stop, len(v) - 1)):
        if (v[j] <= level < v[j+1]) if rising else (v[j] >= level > v[j+1]):
            return float(t[j] + (t[j+1]-t[j]) * (level-v[j])/(v[j+1]-v[j]))
    return np.nan


def detect_peaks(t, v, height=-10., prominence=20., separation_ms=2.):
    dt = float(np.median(np.diff(t)))
    return find_peaks(v, height=height, prominence=prominence,
                      distance=max(1, int(round(separation_ms / (dt*1000)))))[0]


def analyze_events(t, v, start_s, end_s, height=-10., prominence=20.,
                   separation_ms=2., dvdt_threshold=20., ahp_window_ms=50.,
                   ahp_trough_window_ms=3., ahp_post_injection=False):
    t = np.asarray(t, dtype=float)
    v = np.asarray(v, dtype=float)
    if len(t) < 3 or len(t) != len(v) or not np.all(np.isfinite(v)):
        raise ValueError("Voltage must contain at least three finite samples.")
    dt = float(np.median(np.diff(t)))
    if dt <= 0 or start_s >= end_s:
        raise ValueError("Use increasing time and a nonempty analysis window.")
    if ahp_window_ms <= 0 or ahp_trough_window_ms <= 0:
        raise ValueError('AHP search and recovery windows must be positive.')
    tm = t * 1000.
    dv = np.gradient(v, tm)
    peaks = detect_peaks(t, v, height, prominence, separation_ms)
    # Determine thresholds for all events so AHP windows stop before the next AP.
    onsets = []
    previous = -1
    for peak in peaks:
        lo = max(previous + 1, peak - max(2, int(.005/dt)), 0)
        upstroke = lo + int(np.argmax(dv[lo:peak+1]))
        above = np.flatnonzero(dv[lo:upstroke+1] >= dvdt_threshold)
        onset = lo + int(above[0]) if len(above) else None
        onsets.append(onset)
        previous = peak
    rows = []
    for n, peak in enumerate(peaks):
        if not start_s <= t[peak] < end_s:
            continue
        onset = onsets[n]
        row = {"AP": len(rows)+1, "Peak sample": int(peak),
               "SPIKE Peak Membrane Voltage-1 (mV)": float(v[peak]),
               "SPIKE Location (ms)": float(tm[peak]),
               "SPIKE Onset (ms)": np.nan, "SPIKE Rise (ms)": np.nan,
               "SPIKE Width (ms)": np.nan,
               "AHP Peak Membrane Voltage-1 (mV)": np.nan,
               "AHP Location (ms)": np.nan, "AHP Onset (ms)": np.nan,
               "AHP Rise (ms)": np.nan, "AHP Width (ms)": np.nan,
               "Threshold Vm (mV)": np.nan, "AP amplitude (mV)": np.nan,
               "AHP amplitude from threshold (mV)": np.nan,
               "AHP trough Vm (mV)": np.nan, "AHP Rebound (ms)": np.nan,\n               "AHP Rebound latency (ms)": np.nan, "AHP Rebound Vm (mV)": np.nan, "Status": ""}
        if onset is None:
            row["Status"] = "No dV/dt threshold crossing"
            rows.append(row)
            continue
        baseline = float(v[onset])
        next_start = (onsets[n+1] if onsets[n+1] is not None else int(peaks[n+1])) if n+1 < len(peaks) else len(v)-1
        # Bound AP width and AHP by next AP, search window, and analysis end.
        # AHP can continue beyond current injection if explicitly enabled.
        # Never cross another AP or the acquisition boundary.
        analysis_limit = len(v)-1 if ahp_post_injection else int(np.searchsorted(t, end_s))
        stop = min(next_start, analysis_limit, len(v)-1,
                   peak + max(2, int(ahp_window_ms/1000/dt)))
        half = baseline + (v[peak]-baseline)/2.
        left = crossing(tm, v, half, onset, peak, True)
        right = crossing(tm, v, half, peak, stop, False)
        row.update({"SPIKE Onset (ms)": float(tm[onset]),
                    "SPIKE Rise (ms)": crossing(tm, v, baseline+.9*(v[peak]-baseline), onset, peak, True)
                    - crossing(tm, v, baseline+.1*(v[peak]-baseline), onset, peak, True),
                    "SPIKE Rise 10% (ms)": crossing(tm, v, baseline+.1*(v[peak]-baseline), onset, peak, True),
                    "SPIKE Rise 90% (ms)": crossing(tm, v, baseline+.9*(v[peak]-baseline), onset, peak, True),
                    "SPIKE Half rise (ms)": left, "SPIKE Half fall (ms)": right,
                    "_Event start (ms)": float(tm[max(int(peaks[n-1])+1 if n else 0, peak-max(2, int(.005/dt)))]),
                    "_Event end (ms)": float(tm[stop]),
                    "SPIKE Width (ms)": right-left,
                    "Threshold Vm (mV)": baseline,
                    "AP amplitude (mV)": float(v[peak]-baseline)})
        # Limit trough identification only; retain the longer capture/recovery window.
        # The cutoff is anchored to the interpolated AP falling half-height crossing.
        if not np.isfinite(right):
            row["Status"] = "No AP half-fall crossing; AHP search unavailable"
            rows.append(row)
            continue
        trough_end_ms = min(float(tm[stop]), right + ahp_trough_window_ms)
        trough_stop = min(stop, int(np.searchsorted(tm, trough_end_ms, side='right'))-1)
        row["AHP trough search end (ms)"] = trough_end_ms
        # AHP starts when the repolarizing AP crosses back below its threshold Vm.
        ahp_on = crossing(tm, v, baseline, peak, trough_stop, False)
        if not np.isfinite(ahp_on):
            row["Status"] = "No post-AP threshold return in AHP window"
        else:
            first = int(np.searchsorted(tm, ahp_on))
            if trough_stop <= first:
                row["Status"] = "AHP window truncated"
            else:
                trough = first + int(np.argmin(v[first:trough_stop+1]))
                # A boundary minimum is unresolved, not a measured trough.
                if trough >= trough_stop or v[trough] >= baseline:
                    row["Status"] = "No resolved AHP trough before window boundary"
                else:
                    ahalf = baseline + (v[trough]-baseline)/2.
                    down = crossing(tm, v, ahalf, max(peak, first-1), trough, False)
                    up = crossing(tm, v, ahalf, trough, stop, True)
                    row.update({
                        "AHP Peak Membrane Voltage-1 (mV)": float(v[trough]),
                        "AHP Location (ms)": float(tm[trough]),
                        "AHP Onset (ms)": ahp_on,
                        "AHP Rise (ms)": crossing(tm, v, baseline+.9*(v[trough]-baseline), max(peak, first-1), trough, False)
                        - crossing(tm, v, baseline+.1*(v[trough]-baseline), max(peak, first-1), trough, False),
                        "AHP Rise 10% (ms)": crossing(tm, v, baseline+.1*(v[trough]-baseline), max(peak, first-1), trough, False),
                        "AHP Rise 90% (ms)": crossing(tm, v, baseline+.9*(v[trough]-baseline), max(peak, first-1), trough, False),
                        "AHP Half rise (ms)": down, "AHP Half fall (ms)": up,
                        "AHP Width (ms)": up-down,
                        "AHP amplitude from threshold (mV)": float(v[trough]-baseline),
                        "AHP trough Vm (mV)": float(v[trough])})
                    # First post-trough local maximum, excluding one-sample noise reversals.
                    # Require at least two consecutive non-decreasing increments followed
                    # by a decreasing increment; do not call the capture endpoint a peak.
                    # This is a descriptive rebound landmark, not AP firing detection.
                    recovery = v[trough:stop+1]
                    if len(recovery) >= 4:
                        diffs = np.diff(recovery)
                        # A local maximum must show a meaningful fall within the
                        # captured recovery, not just one noisy downward sample.
                        rebound_candidates = [k for k in range(2, len(recovery)-1)
                                              if diffs[k-2] > 0 and diffs[k-1] >= 0 and diffs[k] < 0
                                              and recovery[k] - np.min(recovery[k+1:]) >= 1.0]
                        if rebound_candidates:
                            rebound_idx = trough + rebound_candidates[0]
                            row["AHP Rebound (ms)"] = float(tm[rebound_idx])
                            row["AHP Rebound latency (ms)"] = float(tm[rebound_idx]-tm[trough])
                            row["AHP Rebound Vm (mV)"] = float(v[rebound_idx])
                    row["Status"] = "OK" if np.isfinite(up) else "AHP half-recovery truncated; width unavailable"
        rows.append(row)
    for row in rows:
        for block in ("SPIKE", "AHP"):
            origin = row[block+" Location (ms)"]
            for label in (("Location", "Onset", "Rise 10%", "Rise 90%", "Half rise", "Half fall", "Rebound") if block == "AHP" else ("Location", "Onset", "Rise 10%", "Rise 90%", "Half rise", "Half fall")):
                key = f"{block} {label} (ms)"
                row.setdefault(key, np.nan)
                row[f"{block} {label} relative (ms)"] = row[key]-origin
    return rows
