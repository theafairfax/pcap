# Compare Groups

**Compare Groups** compares kinetics across assigned sets of recordings.

You can use results from the current **Bulk Kinetics** session or upload a previously downloaded 16-column PCAP kinetics CSV. This allows analysis of existing results without reprocessing the source recordings.

Assign each file using the checkbox matrix; each recording belongs to at most one group. Select **Add another group** for additional experimental conditions, then **Analyze** to generate box plots and downloadable summaries.

Time landmarks in comparisons are relative to the AP peak. Durations and amplitudes remain in their measured units.

Where supported, plots report two-sided Welch-test p-values and Holm-adjusted p-values across tested comparisons. **These tests assume independent observations**: paired measurements and recordings clustered by cell or animal require different statistical models. A nonsignificant p-value does not establish equivalence.


## Comparing up to six groups

Compare Groups accepts 2–6 named groups. The group-count selector automatically expands to match group IDs found in the current bulk results or an imported PCAP kinetics CSV. Previously exported two-group CSVs and legacy `True`/`False` group values remain supported. File assignments can also be changed manually; each recording belongs to at most one group.

Every metric provides one boxplot per active group and pairwise Welch comparisons for all group pairs (up to 15 pairs with six groups). Benjamini–Hochberg and Holm adjustments apply across all tested metrics and group pairs. **Prototypical AP/AHP waveforms** overlay up to six landmark-derived curves, each aligned at its AP peak (t = 0); these schematics are *not* averages of raw voltage traces. Two-group waveforms show significance annotations. Three-to-six-group waveforms include a labeled significance table directly beneath the overlaid traces that identifies each significant group pair, landmark, asterisks, and selected adjusted p-value. Combined PNG/PDF plots preserve all pairwise brackets and provide a separate readable Welch/BH/Holm table under every boxplot, rather than overlapping captions. Standalone waveform PNG and combined PNG/PDF exports include all overlaid curves.
