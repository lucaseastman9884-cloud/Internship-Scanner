# Reference data

## 2026_Gaz_place_national.txt
The U.S. Census Bureau's 2026 Gazetteer file for places, unmodified. The scanner reads it offline to get coordinates for a city and state (D-022). It makes no requests at run time.

- **Source:** https://www2.census.gov/geo/docs/maps-data/data/gazetteer/2026_Gazetteer/2026_Gaz_place_national.zip
- **Listed on:** https://www.census.gov/geographies/reference-files/time-series/geo/gazetteer-files.2026.html
- **Columns:** https://www.census.gov/programs-surveys/geography/technical-documentation/records-layout/gaz-record-layouts.html
- **Year:** 2026
- **Downloaded:** 2026-11-02
- **SHA-256 of this file:** e10cb8004732684fa2a75b9d6030c6c9171674d6b112cff29dbc1bc31a9b82fa
- **Reuse:** works of the U.S. Government have no U.S. copyright (17 U.S.C. § 105). The Census Bureau's [TIGER/Line documentation](https://www2.census.gov/geo/pdfs/maps-data/data/tiger/tgrshp2022/TGRSHP2022_TechDoc_Ch1.pdf) says you may reproduce its materials and asks that you cite it as the source. The Gazetteer page itself has no reuse statement, so this is the closest official wording we found.

**Source: U.S. Census Bureau.**

Each coordinate is the place's "internal point": a point inside the place, not necessarily its downtown. That is close enough for radius checks.

To update it, download the newer file, replace this one, change the path in `scanner/gazetteer.py`, and update this README.
