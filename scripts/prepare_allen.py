"""Prepare real Allen Cell Types references in a separate AllenSDK environment.

Example: python scripts/prepare_allen.py --specimen-ids 464212183 --output references/allen.json
No synthetic records are substituted when downloads or detection fail.
"""
import argparse
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import numpy as np
from neuron_compare.core import Settings, first_event, injection_window, count_spikes
from neuron_compare.recordings import Sweep
from neuron_compare.references import save_collection


def prepare_cell(cache, cell, settings):
    specimen=int(cell['id'])
    sweep_metadata=cache.get_ephys_sweeps(specimen)
    eligible=[s for s in sweep_metadata if s.get('stimulus_name','').strip().lower()=='long square'
              and s.get('passed') is not False]
    if not eligible:
        raise ValueError('No eligible Long Square sweeps.')
    data=cache.get_ephys_data(specimen)
    candidates=[]
    for item in eligible:
        number=int(item['sweep_number'])
        raw=data.get_sweep(number)
        voltage=np.asarray(raw['response'],dtype=float)*1000.
        current=np.asarray(raw['stimulus'],dtype=float)*1e12
        t=np.arange(len(voltage),dtype=float)/float(raw['sampling_rate'])
        # Respect the SDK's valid acquisition range (inclusive endpoint).
        first,last=raw.get('index_range',(0,len(t)-1))
        sw=Sweep(number,t[first:last+1]-t[first],voltage[first:last+1],current[first:last+1])
        try:
            lo,hi,source=injection_window(sw,settings)
            if source.startswith('Full sweep'):
                continue
            baseline=sw.current[sw.time<lo]
            middle=sw.current[(sw.time>=lo+.2*(hi-lo))&(sw.time<hi-.2*(hi-lo))]
            if not len(baseline) or not len(middle):
                continue
            amplitude=float(np.median(middle)-np.median(baseline))
            if amplitude>=0 and count_spikes(sw,settings)>0:
                candidates.append((amplitude,number,sw))
        except ValueError:
            continue
    if not candidates:
        raise ValueError('No nonnegative-current spiking Long Square sweep.')
    amplitude,number,sw=min(candidates,key=lambda x:(x[0],x[1]))
    area=cell.get('structure_area_abbrev') or cell.get('structure_area_acronym') or 'Unknown region'
    layer=cell.get('structure_layer_name') or 'Unknown layer'
    line=cell.get('transgenic_line') or 'No transgenic label supplied'
    meta=dict(id=f'allen-{specimen}',label=f'{specimen} · {area} · {line}',
              source='Allen Cell Types Database',source_url=f'https://celltypes.brain-map.org/experiment/electrophysiology/{specimen}',
              species=cell.get('species','Unknown'),region=area,layer=layer,
              cell_type=line,label_evidence='Source transgenic line; not a transcriptomic subtype assignment',
              reporter_status=cell.get('reporter_status'),specimen_id=specimen,synthetic=False,
              selection='First AP in lowest nonnegative-current spiking eligible Long Square sweep',
              injected_current_pa=amplitude,source_sweep=number,recording_time_origin='Start of SDK valid acquisition range',
              temperature_c=None,junction_potential_correction_mv=None)
    return first_event(sw,settings,metadata=meta)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--specimen-ids',type=int,nargs='+')
    parser.add_argument('--limit',type=int,default=5,help='Maximum cells to prepare (and attempt).')
    parser.add_argument('--output',default='references/allen.json')
    parser.add_argument('--cache',default='.allen-cache/manifest.json')
    args=parser.parse_args()
    if args.limit<1:
        parser.error('--limit must be positive')
    try:
        from allensdk.core.cell_types_cache import CellTypesCache
    except ImportError as err:
        raise SystemExit('Install requirements-allen.txt in a separate Python environment first.') from err
    cache=CellTypesCache(manifest_file=args.cache)
    cells=cache.get_cells(species=['Mus musculus'])
    if args.specimen_ids:
        by_id={int(c['id']):c for c in cells}
        unknown=set(args.specimen_ids)-set(by_id)
        if unknown:
            raise SystemExit('IDs not present in mouse Cell Types catalog: '+str(sorted(unknown)))
        cells=[by_id[i] for i in args.specimen_ids]
    events=[]
    for cell in cells[:args.limit]:
        try:
            event=prepare_cell(cache,cell,Settings())
            events.append(event)
            print('Prepared',cell['id'])
        except Exception as err:
            print(f"Skipped {cell['id']}: {err}",file=sys.stderr)
    if not events:
        raise SystemExit('No references prepared. Output was not replaced. Check IDs, API access, and protocols.')
    save_collection(args.output,events)
    print(f'Saved {len(events)} real reference neurons to {args.output}')


if __name__=='__main__':
    main()
