# Kinetics Visualizer

The **Kinetics Visualizer** provides an interactive view of action potential and afterhyperpolarization measurements on individual recordings.

Use it to inspect AP threshold/onset, peak, rise landmarks, half-height crossings, and AHP trough and related markers. Confirm that the selected AP and any AHP trough correspond to the intended biological event, especially when the waveform is noisy or the AHP does not fully recover.

The AHP search looks for the lowest post-AP voltage up to **30 ms after AP half-fall**, stopping sooner at the next AP, injection end, or capture boundary. Later minima do not count as AHP troughs.

For measurement conventions, see [Mathematical Methods](mathematical-methods.md).
