# Bulk Kinetics

**Bulk Kinetics** processes a collection of rheobase recordings and selects the first AP from the first AP-generating sweep of each recording.

After processing, download one of two concise kinetics exports:

- **Absolute kinetics CSV:** event landmarks use the recording sweep's time coordinates (ms).
- **Relative kinetics CSV:** landmark timestamps are expressed relative to the AP peak, so the AP peak is at 0 ms.

Time *durations*, including rise times and half-width, are unchanged between exports. Both exports include identifiers and electrophysiological measurements. Unresolved measurements are left empty rather than inferred.

The bulk workflow also reports processing status to help identify recordings requiring manual review.
