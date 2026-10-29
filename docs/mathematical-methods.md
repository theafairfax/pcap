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

The AHP trough is the selected post-AP voltage minimum in the defined search window. The concise **AHP Half-Fall** export means the **descending, pre-trough** crossing of the voltage midpoint between AHP onset/threshold and trough:

\[
V_{half,AHP} = \frac{V_{onset,AHP}+V_{trough,AHP}}{2}.
\]

It does not require post-trough recovery. The concise AHP amplitude is a *positive depth*, computed as \(V_{threshold,AP}-V_{trough,AHP}\).

These measures are sensitive to baseline choice, injection protocol, filters, sampling frequency, and noise; see [Limitations](limitations.md).
