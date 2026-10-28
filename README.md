# Patch Clamp Analysis Platform

A small Streamlit application for building intuition about individual neuronal
AP/AHP waveforms. Your neuron stays black; the browsed reference appears in gray,
with matching colored measurement intersections. Bulk uploads export per-file
kinetics and support descriptive two-group box plots. Waveform similarity does
not establish cell type or ion-channel identity.

## Start locally

Use Python 3.11 (recommended). From this directory:

```bash
python -m venv .venv
# macOS/Linux:
source .venv/bin/activate
# Windows PowerShell instead: .venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m streamlit run app.py
```

The included synthetic reference collection lets the app start without an Allen
account, SDK installation, network download, or recording upload. Every synthetic
record is visibly labeled and has no biological identity. These are teaching/UI
examples, not sampled neurons or a scientific validation set.

## Deploy from your new GitHub repository

1. Extract this archive. Upload the **contents** of `neuron-compare/` into your new
   repository, so `app.py` and `requirements.txt` are at its root. Include the
   `neuron_compare/`, `references/`, `scripts/`, `.streamlit/` and `tests/` folders.
2. In Streamlit Community Cloud, select that repository and branch, choose
   `app.py`, and select Python 3.11 in deployment settings.
3. Deploy. The main requirements do not install AllenSDK. Real reference JSON
   collections prepared below can be committed to `references/` and redeployed.

The bundle contains application source, not a hosted or already deployed site.
Uploaded experiments are processed in server memory and temporary files are
removed after reading. Bounded Streamlit caches hold parsed data during the
server lifetime. Uploading a file does not publish it as a reference or write it
into the repository. A public deployment still runs on its host's infrastructure.

## The complete user flow

- Upload **one** current-clamp step/rheobase `.abf`, `.axgd` or `.axgx` recording.
- Select a sweep; the default is the first sweep with a detected AP.
- Only the **first AP during that sweep's injection window** and its following
  AHP enter the comparison, even if there are later APs in the sweep.
- Choose AP spike or AHP. Browse the reference list with Previous/Next.
- To compare two recordings, choose **User Uploaded** under **Reference collection → Collection**, upload a second ABF/AXGD/AXGX rheobase recording, and choose its **Reference sweep**. Your original recording stays black and the uploaded reference appears gray in both AP and AHP views. Each sweep contributes its first detected AP/AHP; both files use **Adjust analysis** settings (including any manual injection window). The reference has its own voltage channel selector and defaults to its first spiking sweep. No Supabase configuration is required, and the reference upload is not published.
- Explore your values, the reference values, and `reference minus yours`.

The Kinetics Visualizer has no ramp protocol, RMP-monitor workflow, or required metadata form.
The app assumes the uploaded file is a rheobase/step protocol; it does not infer
or certify the protocol type from a filename. A custom selected sweep can be
suprathreshold; its first AP is still used.

Open **Adjust analysis** only when needed. It contains detection settings,
voltage-channel rank, optional injection start/end, alignment, normalization, and
marker highlighting. **Check source sweep** shows the actual selected trace and
analysis window. Current-derived timing is an approximation for simple steps;
verify it against the trace. If no current step can be resolved, analysis uses
the full sweep; set a manual window to exclude test pulses and rebound spikes.

## Display behavior

- Both AP spike and AHP views show the same interval: **2 ms before AP onset
  through 3 ms after AP half-fall**, limited to available captured samples. Each
  trace uses its own AP landmarks. Display endpoints are interpolated between
  samples. Measurements still use the full analysis/recovery capture. Markers
  outside the visible window remain in the tables but are hidden on the plot.
- Query: black waveform, solid colored marker lines.
- Reference: gray waveform, faint dashed colored marker lines.
- Plotly hover provides detailed values; scrolling the reference selector or
  pressing Previous/Next updates the overlay and comparison table.
- Axes fit the two visible traces, ignoring older collection-wide plot bounds.
  Plot zoom is available; the default range is restored on redraw.
- Alignment is selected beside the waveform: **Peak / trough** puts each AP
  peak or AHP trough at zero; **Onset** puts each event onset at zero. Both
  traces use their own chosen landmark. The chosen landmark stays at zero;
  axis limits follow the visible intervals. Onset alignment requires resolved onset.
- Optional normalization sets AP threshold Vm to zero and divides by the event's
  absolute amplitude. Time is never stretched. Raw values remain in the table.
- Absolute sweep times and times relative to each event's location are shown
  under a collapsed marker table. Unresolved values remain missing.
- This initial release supports automatic markers and highlighting. Direct
  dragging/manual editing of landmarks is not included.

## Measurement definitions (analysis version `first-event-1.1`)

Samples use seconds, mV and pA internally at the reader boundary; the event model
uses milliseconds and mV. All reference and upload events use the same extractor.

- AP detection: SciPy peaks, default minimum -10 mV, prominence 20 mV, separation
  2 ms. These are starting settings and may miss small/atypical events.
- AP location: detected local voltage maximum. Onset: earliest sample at or above
  20 mV/ms before maximum upstroke, within 5 ms of peak and after the prior peak.
  Derivatives use unfiltered voltage; onset remains sensitive to noise/filtering.
- AP amplitude: peak minus onset Vm. Rise: interpolated 10–90% amplitude crossing
  interval. Width: time between rising/falling 50% crossings above onset Vm.
- AHP onset: post-AP downward return through AP onset Vm. Location: subsequent
  minimum. Depth is signed trough minus AP onset Vm, not trough/absolute AP peak.
- AHP rise: downward 10–90% interval from onset toward trough; width: duration
  between downward/upward half-depth crossings. It is not exponential decay tau.
- AHP trough identification stops **3 ms after the AP half-fall** (the interpolated
  falling 50% crossing between AP onset Vm and peak), or earlier at the next AP
  onset, injection-window end, or configured capture limit. A trough at the search
  boundary is unresolved; if AP half-fall is missing, AHP detection is unavailable.
  Recovery measurements and waveform display retain the longer post-peak capture
  (default 50 ms). Truncated recovery yields missing width. This early-trough
  criterion emphasizes fast AHPs and excludes later troughs.
- Version 1.0 local and Supabase references are remeasured from their stored
  waveform samples when loaded, using the new criterion; no re-upload is required.
  New references are saved as version 1.1.
- No junction-potential correction, temperature correction, or automatic
  cross-laboratory harmonization is applied.

These conventions may differ from Allen/IPFX precomputed features, Bean's
illustrated baseline definitions, Clampfit or AxoGraph templates. This app
recomputes reference markers, rather than mixing incompatible feature tables.
Do not interpret the illustrative demo or feature differences as identification.

## Prepare real Allen reference neurons

Preparation is an **optional separate task**, not a prerequisite to run the app.
Use a separate environment because AllenSDK has its own dependency constraints.
Python 3.10 is a reasonable starting environment for that SDK; resolve/test its
requirements independently of the Python 3.11 app environment.

```bash
python3.10 -m venv .venv-allen
source .venv-allen/bin/activate
python -m pip install -r requirements-allen.txt
python scripts/prepare_allen.py --specimen-ids 464212183 --output references/allen.json
# Or attempt the first five mouse cells in the catalog:
python scripts/prepare_allen.py --limit 5 --output references/allen.json
```

The script downloads Cell Types metadata and complete cell NWB recordings into
`.allen-cache/`. Downloads may be large. It considers eligible `Long Square`
sweeps, skips explicitly failed sweeps, selects the lowest nonnegative-current
spiking step, then extracts its first AP/AHP with the app's measurement code.
This is an operational step-rheobase selection, not proof of true physiological
rheobase. Missing QC flags are not assumed to prove QC success. Selected sweep,
current, settings, source ID and labeling evidence are retained.

No arbitrary spikes or synthetic stand-ins are substituted for failed cells.
Failures are printed; if no cells qualify, the output is not overwritten.
Specimen `464212183` comes from the SDK example; availability and eligibility
must be checked by running the script. You can provide other mouse specimen IDs.

### Browse by species and region, then prepare one cell

In the app, choose **Collection → Species → Region → Reference neuron**.
These filters browse records already prepared in the selected JSON collection;
they do not query the entire Allen catalog. Missing species labels appear as
Unknown, and changing species resets incompatible region/reference selections.

To discover source specimen IDs without downloading complete recordings, run
these commands in your Allen environment (Windows PowerShell examples):

```powershell
.\.venv-allen310\Scripts\python.exe scripts\prepare_allen.py --species mouse --list-cells
.\.venv-allen310\Scripts\python.exe scripts\prepare_allen.py --species mouse --regions VISp --list-cells
.\.venv-allen310\Scripts\python.exe scripts\prepare_allen.py --species human --list-cells
```

Use an ID printed in your chosen species/region catalog to prepare a single
reference. For example (the example ID still needs to qualify):

```powershell
.\.venv-allen310\Scripts\python.exe scripts\prepare_allen.py --species mouse --specimen-ids 464212183 --limit 1 --output references\allen_464212183.json
```

For a human specimen, use `--species human` and its actual specimen ID. Region
abbreviations must match the catalog (case-insensitive); no eligible recording
is guaranteed by a metadata listing. `--species all` includes both species.
`--regions` can also restrict preparation, e.g. `--species mouse --regions VISp
--limit 5`. The default remains five mouse cells.

Upload the generated JSON file into your repository's `references/` directory,
restart the app, and select the new collection. A one-cell collection directly
compares that reference with the uploaded neuron. Each output file replaces its
previous contents, so use distinct filenames to keep individual selections.
Full NWB downloads stay local in `.allen-cache/`; only compact reference snippets
are needed by the app. The user upload field accepts the user's ABF/AXGD/AXGX
recording, not raw Allen NWB files or arbitrary JSON.

The app discovers every `references/*.json` collection on restart. It browses
compact prepared snippets and never downloads full NWB files on Previous/Next.
Keep source IDs and provenance when distributing collections. Review applicable
Allen data/software terms before redistribution or other use. The runtime does
not bundle AllenSDK code. Do not assume reporter/transgenic labels establish
transcriptomic identity. Patch-seq/DANDI is a future, separate data adapter.

Official references:
- https://alleninstitute.github.io/AllenSDK/cell_types.html
- https://alleninstitute.github.io/AllenSDK/_static/examples/nb/cell_types.html
- https://github.com/AllenInstitute/AllenSDK
- https://ipfx.readthedocs.io/en/latest/download_data.html

## Files and development

- `app.py`: the complete Streamlit UI.
- `neuron_compare/recordings.py`: ABF/AxoGraph readers with physical-unit checks.
- `neuron_compare/measurements.py`: AP/AHP extraction adapted from your analyzer.
- `neuron_compare/core.py`: first-event selection, settings and comparison values.
- `neuron_compare/plotting.py`: overlay, alignment, fixed axes, marker intersections.
- `neuron_compare/references.py`: strict JSON serialization and collection loading.
- `scripts/prepare_allen.py`: offline reference preparation.
- `scripts/make_demo.py`: reproducible synthetic teaching collection.
- `tests/`: numerical, file-reader, reference-preparation and UI checks.

```bash
python -m unittest discover -s tests -v
python scripts/make_demo.py
```

No live Allen dataset is bundled. Live Allen downloads and real user-recording
comparisons still require validation in your environment. The tests use generated
ABF, mocked unit-aware AxoGraph input, synthetic waveforms and mocked SDK data.

## Provenance

`measurements.py` is adapted from `theafairfax/axgd_analyzer` commit
`4ea866a0782c3b655d13df026e8e64c73d46bdc3` (ABF measurement definitions). Reader
adapters and comparison UI are newly written for this starter. No distribution
license is selected for your new repository; decide one before wider release
and preserve any applicable upstream notices. Version this measurement core
when making scientific-definition changes and regenerate reference collections.

## Supabase reference library (optional)

Follow [the step-by-step Supabase setup](supabase/SETUP.md) to create the catalog,
prepare a varied Allen pilot, upload compact snippets, and add your read-only
connection in Streamlit secrets. The local JSON browser remains available.
Supabase browsing loads metadata first and downloads only the selected waveform;
no AllenSDK dependency is added to the deployed app. The included SQL publishes
reference data for public reading and reserves writes for the local owner-run
importer. Your own uploaded experimental traces are not sent to Supabase.

Existing Supabase waveform files already contain the captured AP/AHP tail and
can be used without re-preparing or re-uploading references. Older catalog plot
bounds may describe the earlier cropped AP view; the browser expands them to
include both displayed traces. Re-uploading a collection recomputes its cohort
bounds for the full AP view and restores fixed full-tail bounds across browsing.


## Bulk Kinetics and Compare Groups

The app has three tabs: **Kinetics Visualizer** (the existing waveform comparison),
**Bulk Kinetics**, and **Compare Groups**. Bulk analysis works independently of
reference collections and uses its own analysis settings.

1. In **Bulk Kinetics**, upload multiple ABF/AXGD/AXGX rheobase files and click
   **Process files**. Files are processed sequentially. The first sweep in recording
   order with a detected AP inside its injection window is selected, then only its
   first AP/AHP is measured. This assumes the rheobase protocol orders sweeps as
   intended; it does not sort by injected current.
2. **Download kinetics CSV** gives one row per file, including filename/unique file
   ID, selected sweep (reader's zero-based index), AP count in that sweep, detection
   settings, injection window, status, and AP/AHP metrics and marker times in ms/mV.
   **AP Half width (ms)** and **AHP Half width (ms)** are half-fall minus half-rise,
   equivalent to the visualizer's half-height width. The 3 ms after AP half-fall
   trough cutoff also applies to bulk analysis. AHP recovery/half-width can extend
   beyond this cutoff within the configured recovery capture.
3. Failed/no-spike files retain an explanatory row; unresolved numbers are blank.
   Partial first events are retained rather than replaced by later APs or sweeps.
   Results cache only scalar rows; parsed recordings are released after each file.
   Streamlit still holds the uploaded file bytes for the current session.
4. In **Compare Groups**, select processed files for **Group 1 files** and **Group 2
   files**, then click **Analyze**. Assignments must be nonempty and disjoint.
   Duplicate filenames are numbered separately. Unselected files are excluded;
   files without any detected AP cannot be selected. Each file contributes one
   observation, even if multiple APs exist in its selected sweep.
5. Box plots compare every standard AP/AHP measure, including both half widths
   and AP-peak-to-AHP-trough delay. Missing values are omitted per measure and n is
   shown separately for each group. The summary reports n, missing count, mean,
   median, and sample SD; it is a descriptive comparison without significance tests.
   Both the summary and the assigned per-file kinetics can be downloaded as CSV.

Changing uploads or bulk settings requires reprocessing. Changing group selections
requires clicking Analyze again before comparison results are shown.

### AHP landmarks (analysis definition `first-event-1.3`)

The AHP kinetics export and visualizer now include **AHP onset time**, **AHP
trough time**, **AHP trough voltage**, **AHP half-fall time**, **AHP rebound
time**, and **AHP rebound latency from trough**. These markers are shown as
sweep-relative times, in milliseconds; trough voltage is in mV.

- **Onset:** first *linearly interpolated* downward crossing of the AP threshold
  voltage following the AP peak.
- **Trough time/voltage:** time and voltage of the lowest *recorded sample* in
  the configured fast/slow trough search window; unresolved boundary minima
  remain missing.
- **Half-fall:** first *linearly interpolated upward recovery* crossing of the
  midpoint between AP threshold voltage and AHP trough voltage. PCAP retains
  its earlier naming: `AHP Half rise` is the downward midpoint crossing,
  and `AHP Half fall` is the upward recovery crossing.
- **Rebound:** first post-trough recorded local maximum after at least two
  non-decreasing recovery increments and a subsequent decrease of at least
  1 mV within the available capture. The time is the sampled maximum; latency
  is rebound time minus trough time. No qualifying maximum means a missing
  value, **not** zero. This heuristic is a descriptive event marker, and may
  also detect an oscillation rather than a genuine ADP; inspect traces.

The AHP plot extends to a detected rebound peak when possible; the AP display
keeps its original window. Bulk CSVs and group box plots include the new
landmarks. Missing rebound peaks do not change an otherwise complete AHP
status to Partial. AHP trough detection remains constrained by the configurable
trough window; rebound detection cannot extend past the captured segment or
next AP. Older saved reference events may not contain these landmarks until
re-analyzed from their originating recordings.
