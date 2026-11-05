# Bulk Kinetics

**Bulk Kinetics** processes a collection of rheobase recordings and selects the first AP from the first AP-generating sweep of each recording.

After processing, download one of two concise kinetics exports:

- **Absolute kinetics CSV:** event landmarks use the recording sweep's time coordinates (ms).
- **Relative kinetics CSV:** landmark timestamps are expressed relative to the AP peak, so the AP peak is at 0 ms.

Time *durations*, including rise times and half-width, are unchanged between exports. Both exports include identifiers and electrophysiological measurements. Unresolved measurements are left empty rather than inferred.

The bulk workflow also reports processing status to help identify recordings requiring manual review.


## Optional group assignment (2–6 groups)

Enable **Assign groups during upload** and select the number of groups (2 through 6). Each group gets its own ABF/AXGD/AXGX upload box. Absolute and AP-peak-relative CSV exports then include a **Group** column with zero-based IDs (`0`–`5`). Without this option, the original 16-column exports remain unchanged. Open Compare Groups to use the preassigned recordings automatically.
