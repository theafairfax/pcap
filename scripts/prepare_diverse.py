"""Seed a modest, reproducible reference collection across source metadata strata."""
import argparse
from collections import defaultdict, deque
import random
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import numpy as np
from scripts.prepare_allen import prepare_cell
from neuron_compare.core import Settings
from neuron_compare.references import load_collection, save_collection


def diverse_order(cells,seed=42):
    groups=defaultdict(list)
    for cell in cells:
        key=(cell.get('species') or 'Unknown',
             cell.get('structure_area_abbrev') or cell.get('structure_area_acronym') or 'Unknown',
             cell.get('structure_layer_name') or 'Unknown',cell.get('transgenic_line') or 'Unknown')
        groups[key].append(cell)
    rng=random.Random(seed)
    for group in groups.values():
        group.sort(key=lambda c:int(c['id']))
        rng.shuffle(group)
    queues=defaultdict(deque)
    for key in sorted(groups):
        queues[key[0]].append(deque(groups[key]))
    # Alternate species, then region/layer/line groups within each species.
    while any(queues.values()):
        for species in sorted(queues):
            if not queues[species]:
                continue
            group=queues[species].popleft()
            yield group.popleft()
            if group:
                queues[species].append(group)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--target',type=int,default=20,help='Total successful cells desired, including a resumed output.')
    parser.add_argument('--max-attempts',type=int,default=60,help='Maximum new candidate cells attempted this run.')
    parser.add_argument('--require-ahp',action='store_true',help='Require a resolved AHP trough; recovery width can remain missing.')
    parser.add_argument('--output',default='references/allen_diverse.json')
    parser.add_argument('--cache',default='.allen-cache/manifest.json')
    args=parser.parse_args()
    if args.target<1 or args.max_attempts<1:
        parser.error('Target and maximum attempts must be positive.')
    from allensdk.core.cell_types_cache import CellTypesCache
    cache=CellTypesCache(manifest_file=args.cache)
    cells=cache.get_cells(species=None)
    events=load_collection(args.output) if Path(args.output).exists() else []
    if any(e['metadata'].get('synthetic') or e['metadata'].get('source')!='Allen Cell Types Database' for e in events):
        raise SystemExit('Output already contains non-Allen records; choose a new filename.')
    seen={int(e['metadata']['specimen_id']) for e in events}
    attempts=0
    print('Alternating available species and region/layer/transgenic-line groups. Not a representative population sample.',flush=True)
    for cell in diverse_order(cells):
        if len(events)>=args.target or attempts>=args.max_attempts:
            break
        if int(cell['id']) in seen:
            continue
        attempts+=1
        try:
            event=prepare_cell(cache,cell,Settings())
            if args.require_ahp and not np.isfinite(event['measurements']['AHP Location (ms)']):
                print(f"Skipped {cell['id']}: AHP trough unresolved",flush=True)
                continue
            events.append(event)
            seen.add(int(cell['id']))
            save_collection(args.output,events)  # checkpoint every successful recording
            print(f"Saved {len(events)}/{args.target}: {event['metadata']['species']} · {event['metadata']['region']} · {cell['id']}",flush=True)
        except Exception as err:
            print(f"Skipped {cell['id']}: {err}",file=sys.stderr,flush=True)
    if not events:
        raise SystemExit('No qualifying references prepared. No output written.')
    print(f'{len(events)} references available in {args.output}; {attempts} new candidates attempted.',flush=True)


if __name__=='__main__':
    main()
