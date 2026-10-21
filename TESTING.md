# Validation notes

Initial starter validation: 10 unittest cases passed.

- First AP selection and manual injection-window exclusion.
- AP/AHP fractional crossings and missing/censored AHP values.
- Strict reference JSON round-trip.
- Generated ABF units, sweep-relative time and scaling.
- Unit-aware mocked AxoGraph channels and temporary-file cleanup.
- Mocked Allen SDK selection of the lowest spiking step.
- Streamlit reference navigation, AHP view, fixed axes, and an uploaded generated ABF defaulting to the first spiking sweep.

Local test environment: Python 3.12.14. CI is configured for Python 3.11; that CI run has not been executed here.

| Package | Tested version |
|---|---|
| streamlit | 1.66.1 |
| plotly | 6.9.0 |
| numpy | 2.3.5 |
| pandas | 2.2.3 |
| scipy | 1.17.0 |
| neo | 0.14.6 |
| quantities | 0.16.4 |
| pyabf | 2.3.8 |

Python compilation and dependency consistency checks also passed. Live Allen API downloads and genuine biological ABF/AXGD samples were not validated for this starter. Synthetic waveforms and a mocked AxoGraph reader do not establish real-world detection accuracy.
