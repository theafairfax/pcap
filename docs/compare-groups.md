# Compare Groups

**Compare Groups** compares kinetics across assigned sets of recordings.

You can use results from the current **Bulk Kinetics** session or upload a previously downloaded 16-column PCAP kinetics CSV. This allows analysis of existing results without reprocessing the source recordings.

Assign each file using the checkbox matrix; each recording belongs to at most one group. Select **Add another group** for additional experimental conditions, then **Analyze** to generate box plots and downloadable summaries.

Time landmarks in comparisons are relative to the AP peak. Durations and amplitudes remain in their measured units.

Where supported, plots report two-sided Welch-test p-values and Holm-adjusted p-values across tested comparisons. **These tests assume independent observations**: paired measurements and recordings clustered by cell or animal require different statistical models. A nonsignificant p-value does not establish equivalence.
