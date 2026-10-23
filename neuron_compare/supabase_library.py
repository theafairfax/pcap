"""Small REST adapter. The app uses a read-only publishable/anon key."""
import base64
import hashlib
import io
import json
import re
import urllib.error
import urllib.parse
import urllib.request
import zipfile
import numpy as np
from .core import ANALYSIS_VERSION, LEGACY_ANALYSIS_VERSION, coordinates
from .references import clean, parse_collection

BUCKET = 'pcap-references'
TABLE = 'pcap_reference_neurons'


def validate_browser_key(key):
    if key.startswith('sb_publishable_'):
        return
    if key.startswith('eyJ'):
        try:
            payload=key.split('.')[1]
            claims=json.loads(base64.urlsafe_b64decode(payload+'='*(-len(payload)%4)))
            if claims.get('role')=='anon':
                return
        except (ValueError,IndexError):
            pass
    raise ValueError('Use a publishable or legacy anon key for browsing; keep owner secret keys in the local importer.')


def request(url, key, endpoint, data=None, method='GET', headers=None):
    url=url.rstrip('/')
    parsed=urllib.parse.urlsplit(url)
    if parsed.scheme!='https' or not parsed.netloc or parsed.path or parsed.query:
        raise ValueError('Use the HTTPS Project URL, with no path or query.')
    auth={'apikey':key}
    # Legacy anon/service-role keys are JWTs. New publishable/secret keys are not.
    if key.startswith('eyJ'):
        auth['Authorization']='Bearer '+key
    auth.update(headers or {})
    req=urllib.request.Request(url+endpoint,data=data,method=method,headers=auth)
    try:
        with urllib.request.urlopen(req,timeout=60) as response:
            content=response.read(8*1024*1024+1)
            if len(content)>8*1024*1024:
                raise ValueError('Supabase response exceeds the 8 MB reference limit.')
            return content
    except urllib.error.HTTPError as err:
        # Do not print request headers or credentials.
        raise ValueError(f'Supabase HTTP {err.code}. Check the URL, key, setup SQL and access policies.') from None
    except urllib.error.URLError:
        raise ValueError('Could not connect to Supabase; retry or check the Project URL.') from None


def catalog(url, key):
    rows=[]
    for offset in range(0,1000000,500):
        params=urllib.parse.urlencode(dict(select='id,label,species,region,analysis_version,storage_path,metadata,plot_bounds',
                                          analysis_version=f'in.({ANALYSIS_VERSION},{LEGACY_ANALYSIS_VERSION})',order='id.asc',limit=500,offset=offset))
        page=json.loads(request(url,key,'/rest/v1/'+TABLE+'?'+params))
        if not isinstance(page,list):
            raise ValueError('Unexpected Supabase catalog response.')
        rows.extend(page)
        if len(page)<500:
            return rows
    raise ValueError('Catalog is too large for this initial browser; narrow the server-side query.')


def encode_event(event):
    record={k:v for k,v in event.items() if k not in ('time_ms','voltage_mv')}
    output=io.BytesIO()
    # Keep float64 samples; compression changes representation, not precision.
    np.savez_compressed(output,time_ms=np.asarray(event['time_ms'],dtype=np.float64),
                        voltage_mv=np.asarray(event['voltage_mv'],dtype=np.float64),
                        record=np.array(json.dumps(clean(record),allow_nan=False,separators=(',',':'))))
    return output.getvalue()


def decode_event(content):
    with zipfile.ZipFile(io.BytesIO(content)) as archive:
        if sum(item.file_size for item in archive.infolist())>32*1024*1024:
            raise ValueError('Expanded reference is too large.')
    with np.load(io.BytesIO(content),allow_pickle=False) as data:
        event=json.loads(str(data['record'].item()))
        event['time_ms']=data['time_ms'].copy()
        event['voltage_mv']=data['voltage_mv'].copy()
    return parse_collection({'schema_version':1,'events':[event]})[0]


def fetch_event(url,key,row):
    path=urllib.parse.quote(row['storage_path'],safe='/')
    content=request(url,key,'/storage/v1/object/public/'+BUCKET+'/'+path)
    event=decode_event(content)
    if event['metadata']['id']!=row['id']:
        raise ValueError('Reference identity does not match the catalog.')
    return event


def upload_event(url,key,event):
    if event['metadata'].get('synthetic') or event['metadata'].get('source')!='Allen Cell Types Database':
        raise ValueError('This importer accepts prepared Allen Cell Types references only.')
    content=encode_event(event)
    uid=str(event['metadata']['id'])
    if not re.fullmatch(r'allen-\d+',uid):
        raise ValueError('Expected an Allen specimen ID.')
    path=f'{ANALYSIS_VERSION}/{uid}/{hashlib.sha256(content).hexdigest()[:24]}.npz'
    # Content-addressed immutable paths make repeats safe and avoid stale caches.
    request(url,key,'/storage/v1/object/'+BUCKET+'/'+path,data=content,method='POST',
            headers={'Content-Type':'application/octet-stream','x-upsert':'true','cache-control':'31536000'})
    bounds={}
    for block in ('SPIKE','AHP'):
        for mode in ('Event location','Event onset'):
            for normalize in (False,True):
                try:
                    x,y,*_=coordinates(event,block,mode,normalize)
                    if len(x):
                        bounds[f'{block}|{mode}|{normalize}']=[float(x.min()),float(x.max()),float(y.min()),float(y.max())]
                except ValueError:
                    continue
    meta=clean(event['metadata'])
    row=dict(id=uid,label=meta.get('label',uid),species=meta.get('species') or 'Unknown',
             region=meta.get('region') or 'Unknown',analysis_version=ANALYSIS_VERSION,storage_path=path,
             metadata=meta,plot_bounds=bounds)
    body=json.dumps(row,allow_nan=False).encode()
    request(url,key,'/rest/v1/'+TABLE+'?on_conflict=id',data=body,method='POST',
            headers={'Content-Type':'application/json','Prefer':'resolution=merge-duplicates,return=minimal'})
    return len(content)
