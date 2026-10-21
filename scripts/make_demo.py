"""Create clearly labeled synthetic references, not biological reference data."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import numpy as np
from neuron_compare.recordings import Sweep
from neuron_compare.core import first_event
from neuron_compare.references import save_collection


def demo_event(width=1., depth=12., name='Demo'):
    t=np.arange(0.,.1,.00002)
    knots=np.array([0,18,19,20,21,24,40,100.],dtype=float)
    knots[2:5]=20+(knots[2:5]-20)*width
    v=np.interp(t*1000,knots,[-65,-65,-60,30,-65,-65-depth,-65,-65])
    return first_event(Sweep(0,t,v),metadata=dict(id=name,label=name,source='Synthetic demonstration',
                        species='Synthetic',region='Not biological data',cell_type='Unlabeled',synthetic=True))


if __name__=='__main__':
    root=Path(__file__).resolve().parents[1]
    save_collection(root/'references/demo.json', [demo_event(.65,8,'Demo A — narrow'),demo_event(1.,12,'Demo B — medium'),demo_event(1.45,18,'Demo C — broad')])
