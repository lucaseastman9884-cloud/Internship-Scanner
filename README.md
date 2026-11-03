# Internship-Scanner

A $0 system that collects finance, banking, accounting, investment, insurance, and risk internships from legitimate sources, keeps their history, and sends a morning email of new matches.

**Status:** Phase 5 (morning email). See [docs/STATUS.md](docs/STATUS.md). How the daily run works: [docs/AUTOMATION.md](docs/AUTOMATION.md).

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

`python -m scanner run` fetches jobs and updates the `data/` folder. It takes about 35 to 60 minutes, because it waits between requests on purpose. `pytest` runs the tests and never uses the network.

## The morning email
After each daily scan on GitHub, the scanner emails a summary: new listings, upcoming deadlines, top open matches, remote Iowa listings, companies to check by hand, and source health. It uses Gmail with an app password, set as three GitHub secrets: `SMTP_USERNAME`, `SMTP_APP_PASSWORD` and `EMAIL_TO`. [docs/AUTOMATION.md](docs/AUTOMATION.md) section 10 shows how to add them.

To preview it locally without sending anything:

```
python -m scanner email --dry-run
```

Then open `outputs/email_preview.html` in a browser. `outputs/` is never committed.

## What's in `data/`
- `internships.json`: every listing we've kept. It changes only when a listing changes, so its history is meaningful.
- `last_seen.json`: the date each listing was last on its board. It's separate so that a daily date doesn't rewrite `internships.json`.
- `companies_status.json`: each company's last check, health, and careers link.
- `meta.json`: the latest run's counts, requests per host, the companies to check by hand, and when the last email was sent.
- `geocache.json`: saved geocoding answers. Empty, because geocoding is off.
- `reference/`: the Census Gazetteer file used for coordinates. Source: U.S. Census Bureau. See its [README](data/reference/README.md).

## Coordinates
Coordinates come from the U.S. Census Bureau's Gazetteer file, read offline (D-022 in [docs/DECISIONS.md](docs/DECISIONS.md)). The Nominatim geocoder is off (`geocoding.enabled: false`), because its robots.txt disallows `/search`.

## Before you work locally
A bot saves to `main` on GitHub every time listings change. So click **Fetch origin**, then **Pull origin**, in GitHub Desktop first. [docs/AUTOMATION.md](docs/AUTOMATION.md) explains why.

## Change settings
Edit [config/config.yaml](config/config.yaml) for cities, seasons, and keywords, and [config/companies.yaml](config/companies.yaml) for companies. A bad value stops the run with a message saying what to fix.

## More
- What we're building: [docs/SPEC.md](docs/SPEC.md)
- The plan: [docs/PLAN.md](docs/PLAN.md)

This repo is public. Never commit keys, passwords, email addresses, phone numbers, resumes, or contact data.
