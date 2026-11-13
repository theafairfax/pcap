# Compare Groups

**Compare Groups** compares kinetics across assigned sets of recordings.

You can use results from the current **Bulk Kinetics** session or upload a previously downloaded PCAP kinetics CSV (legacy 16-column or new 18-column). This allows analysis of existing results without reprocessing the source recordings.

Assign each file using the checkbox matrix; each recording belongs to at most one group. Select **Add another group** for additional experimental conditions, then **Analyze** to generate box plots and downloadable summaries.

Time landmarks in comparisons are relative to the AP peak. Durations and amplitudes remain in their measured units. **AP peak Vm** and **AHP trough Vm** each get their own group boxplot, using the same Welch/BH/Holm procedures as the other measures. Older CSVs without absolute Vm remain compatible: these plots show missing measurements rather than inferring voltages. Absolute voltages are excluded from the landmark-derived prototypical waveforms, which remain threshold-relative.

Where supported, plots report two-sided Welch-test p-values and Holm-adjusted p-values across tested comparisons. **These tests assume independent observations**: paired measurements and recordings clustered by cell or animal require different statistical models. A nonsignificant p-value does not establish equivalence.


## Comparing up to six groups

Compare Groups accepts 2–6 named groups. The group-count selector automatically expands to match group IDs found in the current bulk results or an imported PCAP kinetics CSV. Previously exported two-group CSVs and legacy `True`/`False` group values remain supported. File assignments can also be changed manually; each recording belongs to at most one group.

Every metric provides one boxplot per active group and pairwise Welch comparisons for all group pairs (up to 15 pairs with six groups). Benjamini–Hochberg and Holm adjustments apply across all tested metrics and group pairs. **Prototypical AP/AHP waveforms** overlay up to six landmark-derived curves, each aligned at its AP peak (t = 0); these schematics are *not* averages of raw voltage traces. Two-group waveforms show significance annotations. Three-to-six-group waveforms include a labeled significance table directly beneath the overlaid traces that identifies each significant group pair, landmark, asterisks, and selected adjusted p-value. Combined PNG/PDF plots preserve all pairwise brackets and provide a separate readable Welch/BH/Holm table under every boxplot, rather than overlapping captions. Standalone waveform PNG and combined PNG/PDF exports include all overlaid curves.

## Analysis results organized into three tabs

After **Analyze**, results are displayed in **Protowaveform**, **Kinetics Measurements**, and **Voltage Measurements** tabs. Kinetics plots are measured in milliseconds (including times relative to the AP peak and durations), while voltage plots are measured in millivolts (including threshold-relative AP/AHP amplitudes and absolute peak/trough Vm). Each collection of boxplots has its own downloadable combined PNG and PDF. The numerical pairwise tests and summary CSVs remain downloadable beneath the tabs.

The **Protowaveform** tab provides two independent landmark-derived visualizations:

- **Threshold-normalized:** AP onset is defined as 0 mV; group-mean AP amplitude and positive AHP depth determine the heights, as in earlier versions.
- **Raw membrane voltage:** Uses group-mean AP onset voltage, raw AP peak voltage, and raw AHP trough voltage as voltage anchors, with intermediate landmark voltages interpolated between them. To avoid mixing missing values into different anchors, only recordings with all three voltages contribute to a raw-voltage profile. From older CSV files lacking raw voltage fields, this profile is unavailable and never fabricated.

In both visualizations, timing is anchored to each AP peak at 0 ms. Curves are shape-preserving interpolations of mean landmarks, **not** averages of sampled ABF traces. The two visualizations have separate downloadable PNGs. Voltage significance annotations are matched to the plot's own voltage units: threshold-relative amplitude tests on the normalized figure, raw Vm tests on the raw figure.

## AHP trough resolution as a categorical outcome

Under **Voltage Measurements**, a stacked-percentage chart shows the counts and percentages of AP-positive recordings in each group with **resolved** and **unresolved** AHP troughs. A resolved trough requires a valid AHP trough location and depth; full AHP recovery/half-width is not required. No-AP files and processing errors are excluded from the denominator and explicitly counted as exclusions.

The omnibus **Pearson chi-squared** test compares the group-by-resolution contingency table; the results report its degrees of freedom, p-value, and smallest expected cell count. When the table is 2×2 and expected counts are under five, **Fisher's exact** p-value is also given because chi-squared's approximation can be unreliable. When a group has no eligible files, or only one resolution outcome appears across all groups, the chi-squared p-value is unavailable. For 3–6 groups with sparse cells, seek an exact or Monte Carlo contingency test before interpreting significance.

**Important:** an unresolved trough means the algorithm could not identify a trough using the configured bounds and settings, **not** proof that the neuron lacks an afterhyperpolarization. The proportions are sensitive to the detection window, filtering, and recording quality, and the tests assume independent recordings.

## Voltage Measurements order

The eight voltage panels appear in this order: (1) Average RMP (raw mV), (2) AP onset Vm (raw mV), (3) AP peak Vm (raw mV), (4) AHP trough Vm (raw mV), (5) AP peak above AP onset (positive mV), (6) AHP trough depth below AP onset (positive mV), (7) AP peak minus average RMP (signed mV), and (8) AHP trough minus average RMP (signed mV). Multiplicity corrections span the numerical comparisons and all group pairs.

Each boxplot contributes **one recording**, not each sweep used to estimate that recording's RMP. Missing RMPs are excluded only from RMP-dependent panels. Older CSVs without these values can show empty panels; process the original recordings for complete values.
