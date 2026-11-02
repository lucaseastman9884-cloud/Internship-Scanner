# Internship-Scanner

A $0 system that collects finance, banking, accounting, investment, insurance, and risk internships from legitimate sources, keeps their history, and sends a morning email of new matches.

**Status:** Phase 3 (full pipeline). See [docs/STATUS.md](docs/STATUS.md).

## Set up (one time)
Open Terminal and run these one at a time:

```
cd ~/Documents/GitHub/Internship-Scanner
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

The virtual environment (`.venv`) keeps this project's packages separate from the rest of your Mac. When it is active, your Terminal prompt starts with `(.venv)`.

## Run it
In a new Terminal window, turn the environment back on first:

```
cd ~/Documents/GitHub/Internship-Scanner
source .venv/bin/activate
python -m scanner run
pytest
```

`python -m scanner run` fetches jobs and updates the `data/` folder. It takes about 25 to 50 minutes, because it waits between requests on purpose. `pytest` runs the tests and never uses the network.

## What's in `data/`
- `internships.json`: every listing we've kept. It changes only when a listing changes, so its history is meaningful.
- `last_seen.json`: the date each listing was last on its board. It's separate so that a daily date doesn't rewrite `internships.json`.
- `companies_status.json`: each company's last check, health, and careers link.
- `meta.json`: the latest run's counts, requests per host, and the companies to check by hand.
- `geocache.json`: saved geocoding answers. Empty while geocoding is off.

## Geocoding
Geocoding is off (`geocoding.enabled: false`) until decision D-022 in [docs/DECISIONS.md](docs/DECISIONS.md) is made. If it's turned on, results come from Nominatim, © OpenStreetMap contributors, under the [Nominatim usage policy](https://operations.osmfoundation.org/policies/nominatim/).

## Change settings
Edit [config/config.yaml](config/config.yaml) for cities, seasons, and keywords, and [config/companies.yaml](config/companies.yaml) for companies. A bad value stops the run with a message saying what to fix.

## More
- What we're building: [docs/SPEC.md](docs/SPEC.md)
- The plan: [docs/PLAN.md](docs/PLAN.md)

This repo is public. Never commit keys, passwords, email addresses, phone numbers, resumes, or contact data.
