# Limitations and Quality Control

PCAP is a research analysis aid, not an automatic guarantee that every detected physiological event is valid.

- **Sampling rate:** finite sampling and filtering affect derivative-based AP onset, peak location, rise duration, and other submillisecond estimates.
- **Injected current:** apparent AHP depth can depend on the stimulation protocol, selected sweep, voltage baseline, and cellular state. Compare current levels or rheobase alongside AHP kinetics when interpreting group differences.
- **AHP boundaries:** trough identification is constrained by the configured search window. A window boundary minimum may be unresolved rather than a genuine trough.
- **Missing values:** incomplete AP/AHP measurements should remain missing; verify partial results rather than substituting zero.
- **Independence:** standard between-group tests are not valid substitutes for paired or hierarchical statistics when the same neuron or animal contributes multiple observations.

Inspect the original electrophysiology traces for suspicious points and report acquisition settings alongside exported analysis results.
