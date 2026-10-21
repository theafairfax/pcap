# Connect PCAP to your Supabase project

Run the schema in your project, prepare references locally, upload the compact
results, then configure the app's read-only connection. Your uploaded experimental
recordings remain in the existing local processing path; these instructions
publish only reference data you intentionally import.

## 1. Update the project files on your computer

Merge the Supabase integration PR. Download the updated repository ZIP and extract
it, or pull the changes. Open PowerShell in the folder containing `app.py`.

```powershell
Test-Path scripts\prepare_diverse.py
Test-Path scripts\upload_supabase.py
Test-Path supabase\setup.sql
```

All three should return True. Keep using your existing Allen Python environment
if it is in that folder. If this is a newly extracted folder, create it again:

```powershell
py -3.10 -m venv .venv-allen310
.\.venv-allen310\Scripts\python.exe -m pip install --upgrade pip setuptools wheel
.\.venv-allen310\Scripts\python.exe -m pip install -r requirements-allen.txt
```

No new Supabase or Plotly package is needed in the Allen environment for these
scripts. Preparation and upload use your installed NumPy/SciPy plus Python's
standard library.

## 2. Create the catalog and bucket

In your open Supabase project, open SQL Editor, create a new query, paste all of
`supabase/setup.sql`, and run it. It creates:

- `public.pcap_reference_neurons`: searchable species/region catalog.
- `pcap-references`: a public-read Storage bucket holding compressed snippets.
- Read-only catalog access for the app; writes require your owner credential.

Table Editor should show the empty table. Storage should show the bucket. Run
the setup once before uploading. The script can be rerun; an existing bucket's
settings are not changed. If that bucket already existed, verify Public is on
and application/octet-stream uploads are allowed.

Published reference snippets and metadata will be publicly readable. Do not put
private experiments into this bucket. The importer rejects synthetic/non-Allen
collections.

## 3. Prepare a small but varied pilot

```powershell
.\.venv-allen310\Scripts\python.exe scripts\prepare_diverse.py --target 20 --max-attempts 60 --require-ahp --output references\allen_diverse.json
```

This alternates available species and region/layer/transgenic-line groups. It
attempts up to 60 candidate cells to obtain a total of 20 successful cells with
resolved AHP troughs. It does not guarantee equal groups, cell types, or a
representative biological population. Allen's source collection has limited
anatomical coverage, especially cortex; this will not create a whole-brain atlas.
The selection is reproducible from the same catalog, subject to recording
availability and QC. No cell identity is inferred from the waveform.

The script downloads complete NWB recordings into `.allen-cache/`; this can take
time and local disk space. Each successful cell is checkpointed immediately.
Rerunning the command resumes from existing successes. Unsuccessful cells are
reported and may be attempted again on the next run. Remove `--require-ahp` if
you also want AP-only references with explicitly unresolved AHPs. A resolved
trough still does not guarantee resolved AHP recovery width.

To inspect specific catalog choices or prepare one neuron, the earlier
`prepare_allen.py --species ... --regions ... --list-cells` and
`--specimen-ids ...` commands remain available. Upload any resulting Allen
collection with the next step.

## 4. Upload the prepared collection

Open the project's Connect dialog or Settings to find the HTTPS Project URL and
API keys. Use your project's **secret key** (`sb_secret_...`) for this owner-run
local importer; an older `service_role` key also works. Do not use the database
password, personal access token, or publishable key for uploading.

Run:

```powershell
.\.venv-allen310\Scripts\python.exe scripts\upload_supabase.py references\allen_diverse.json
```

The script asks for the Project URL and then prompts for the secret key with
input hidden. The secret is not written into project files or printed. Do not
paste it into chat, GitHub, or Streamlit's publishable-key field.

Each cell uploads a compressed float64 waveform file (precision preserved), then
upserts its catalog row. Re-running does not create duplicate catalog cells.
Content-addressed paths prevent old cached waveforms being confused with new
versions. Reprocessing a changed event can leave a previous unused object in
Storage; the initial importer does not delete older versions automatically.
If metadata writing fails after storage succeeds, rerun to repair the catalog.

You can import an existing collection first as a quick connectivity check:

```powershell
.\.venv-allen310\Scripts\python.exe scripts\upload_supabase.py references\allen.json
```

After uploading, Table Editor should show rows with species, region, source IDs
and storage paths. Storage should show `.npz` objects under the analysis-version
folder. These files are compressed NumPy arrays, not full source recordings.

## 5. Connect Streamlit

In Streamlit Community Cloud, open your app's settings and Secrets. Add:

```toml
[supabase]
url = "https://YOUR_PROJECT_REF.supabase.co"
publishable_key = "sb_publishable_YOUR_KEY"
```

Use the **publishable key**, which receives SELECT access only under the setup
SQL. A legacy `anon` key is also supported. The uploader's secret/service_role
key is not needed by the app. For local Streamlit runs put the same configuration
in `.streamlit/secrets.toml`, which is excluded from Git.

Save and restart the app. Choose **Supabase library** under Collection. The
browser loads catalog metadata, lets you filter Species and Region, and loads
only the selected reference waveform. Previous/Next loads one at a time, with a
bounded cache. Use Refresh cloud library after new uploads (catalog also expires
after 60 seconds). The experiment upload remains your own ABF/AXGD/AXGX recording.

Cloud plot bounds are precomputed during upload so the axis can stay fixed for
the filtered cohort without downloading all its waveforms. Both alignment modes
remain centered at zero. The initial catalog adapter fetches metadata in pages;
it is not a full server-side search engine for arbitrarily large collections.

## 6. Expand once the pilot works

```powershell
.\.venv-allen310\Scripts\python.exe scripts\prepare_diverse.py --target 100 --max-attempts 240 --require-ahp --output references\allen_diverse.json
.\.venv-allen310\Scripts\python.exe scripts\upload_supabase.py references\allen_diverse.json
```

Monitor Supabase Storage and database usage. Full NWB cache files stay local; do
not upload `.allen-cache/`, virtual environments, or credentials. Prepared JSON
files need not be committed to GitHub once the cloud collection is working.

Validation: all 19 automated tests pass. Tests cover codec round trips, catalog pagination,
read-only app browsing, selected-only waveform retrieval, and diverse-order
selection using local/mocked data. This code has not been connected to your
Supabase project or validated against live Allen downloads here. If a request
fails, share its error message rather than any keys.
