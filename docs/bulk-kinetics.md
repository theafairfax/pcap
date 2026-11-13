# Bulk Kinetics

**Bulk Kinetics** processes a collection of rheobase recordings and selects the first AP from the first AP-generating sweep of each recording.

After processing, download one of two concise kinetics exports:

- **Absolute kinetics CSV:** event landmarks use the recording sweep's time coordinates (ms).
- **Relative kinetics CSV:** landmark timestamps are expressed relative to the AP peak, so the AP peak is at 0 ms.

Each export contains the original 16 fields plus **AP peak Vm (mV)** and **AHP trough Vm (mV)**. These two fields are the directly sampled, absolute membrane voltages; unlike the landmark timestamps, they are **identical in both exports**. AP amplitude remains peak minus AP threshold, and AHP amplitude remains the positive depth from AP threshold to the trough. Older 16-column CSVs are still importable, with unavailable absolute voltages left blank.

The AHP trough search defaults to **30 ms after AP half-fall** (also the maximum), matching Kinetics Visualizer. Bulk Kinetics allows a shorter cutoff, down to 1 ms. The search can stop earlier at the next AP or a recording/capture boundary; bulk can optionally include post-injection samples. Inspect late troughs for slow drift.

Time *durations*, including rise times and half-width, are unchanged between exports. Both exports include identifiers and electrophysiological measurements. Unresolved measurements are left empty rather than inferred.

The bulk workflow also reports processing status to help identify recordings requiring manual review.


## Optional group assignment (2–6 groups)

Enable **Assign groups during upload** and select the number of groups (2 through 6). Each group gets its own ABF/AXGD/AXGX upload box. Absolute and AP-peak-relative CSV exports then include a **Group** column with zero-based IDs (`0`–`5`). Without this option, the exports contain 18 columns (the original 16 plus the two membrane voltages). Open Compare Groups to use the preassigned recordings automatically.
