"""Upload compact Allen references. Run locally, never in a public browser."""
import argparse
import getpass
import glob
import os
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from neuron_compare.references import load_collection
from neuron_compare.supabase_library import upload_event


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('files',nargs='+',help='Prepared reference JSON paths or glob patterns.')
    args=parser.parse_args()
    url=os.environ.get('SUPABASE_URL') or input('Supabase HTTPS Project URL: ').strip()
    key=os.environ.get('SUPABASE_SECRET_KEY') or getpass.getpass('Supabase secret/service_role key (hidden): ').strip()
    if key.startswith('sb_publishable_'):
        raise SystemExit('Import needs your project secret key, not its publishable key.')
    paths=sorted({p for pattern in args.files for p in glob.glob(pattern)})
    if not paths:
        raise SystemExit('No matching reference JSON files.')
    events={}
    for path in paths:
        for event in load_collection(path):
            events[event['metadata']['id']]=event
    # Validate every source before any upload.
    for event in events.values():
        if event['metadata'].get('synthetic') or event['metadata'].get('source')!='Allen Cell Types Database':
            raise SystemExit('Remove demo/non-Allen collections from the input files.')
    total=0
    for event in events.values():
        try:
            size=upload_event(url,key,event)
            total+=size
            print(f"Uploaded {event['metadata']['id']}: {size/1024:.1f} KB")
        except Exception as err:
            raise SystemExit(str(err)+'\nPreviously uploaded rows are retained. Re-running is safe.') from None
    print(f'Finished: {len(events)} references; {total/1024:.1f} KB of waveform files.')


if __name__=='__main__':
    main()
