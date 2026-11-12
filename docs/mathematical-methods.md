# Mathematical Methods

## Sampling and numerical estimates

PCAP uses sampled membrane voltage and time values. The nominal sample interval is \(\Delta t = 1/f_s\). Events faster than a few sample intervals are susceptible to temporal-resolution limits. A numerical crossing between adjacent samples \((t_0,V_0)\) and \((t_1,V_1)\) is estimated by linear interpolation:

\[
t_{cross} = t_0 + (t_1-t_0)\frac{V_{target}-V_0}{V_1-V_0}.
\]

This estimates a crossing; it does not reconstruct an unobserved waveform between samples.

## Action potential

AP onset is associated with the configured rising \(dV/dt\) threshold; peak is the maximum recorded voltage in the detected event. AP rise 10% and 90% are voltage crossings referenced to the onset-to-peak voltage difference. AP half-width is the time between the rising and falling half-height crossings.

## Afterhyperpolarization

**Absolute AP peak Vm** is the actual sampled membrane voltage at the detected AP peak, \(V(t_{peak})\). **Absolute AHP trough Vm** is the sampled voltage at the detected AHP minimum, \(V(t_{trough})\). These are not baseline-subtracted values and are unchanged in relative-time exports. The AP amplitude is \(V(t_{peak})-V_{threshold}\).

The AHP trough is the selected post-AP voltage minimum in the defined search window. Specifically, PCAP finds the falling AP half-height crossing, searches for the subsequent downward crossing of the AP onset/threshold voltage, and then chooses the **lowest recorded voltage** after that crossing and no later than the configurable AHP trough cutoff (default 3 ms after AP half-fall). The window is also limited by the next AP, acquisition/capture bounds, and (unless allowed) injection end. A minimum at the search-window boundary, or one that does not fall below threshold, is treated as unresolved. This is a minimum-voltage rule, **not** a first \(dV/dt=0\) rule. The AHP onset/threshold reference is the AP onset voltage, not an independently inferred resting membrane potential. The concise **AHP Half-Fall** export means the **descending, pre-trough** crossing of the voltage midpoint between AHP onset/threshold and trough:

\[
V_{half,AHP} = \frac{V_{onset,AHP}+V_{trough,AHP}}{2}.
\]

It does not require post-trough recovery. The concise AHP amplitude is a *positive depth*, computed as \(V_{threshold,AP}-V_{trough,AHP}\).

These measures are sensitive to baseline choice, injection protocol, filters, sampling frequency, and noise; see [Limitations](limitations.md).
