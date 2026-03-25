# Le Vélib' d'Emmanuel Grégoire — #90157

Interactive map tracking the movements of bike #90157 — the Vélib' that Emmanuel Grégoire, newly elected mayor of Paris, rode from his campaign headquarters to the Hôtel de Ville on election night (22 March 2026).

The Twitter account [@le_velib_a_greg](https://x.com/le_velib_a_greg) now tracks this specific bike's location. This project visualizes all its trips on an animated map.

## Features

- Animated dot traces each route with colored segments per trip
- Multi-day timeline with day tabs and a scrubbable time bar
- Ride vs. parked time shown on the scrubber (colored = riding, gap = parked)
- Other days' routes shown in subtle gray behind the active day
- Auto-updates hourly via GitHub Actions

## Route taken on Sunday 22 March

Route inferred from TV program (https://www.france.tv/info/emission-politique/8261610-municipales-2nd-tour.html): start at Jean Jaurès - Bouret, go to 48.8773, 2.3658 (cross the bridge Rue Eugène Varlin), then go against the one-way until 48.8729, 2.3637, cross the bridge Rue de Lancry, go from there to Bastille, go from there to Hôtel de Ville. Thanks to Florian Sikora for helping with this since I don't know the area around Canal Saint-Martin too well.

## Data pipeline

A GitHub Action runs `poll.py` every hour:
1. Fetches latest rides from [velibest.fr](https://velibest.fr/)
2. Resolves station IDs to names/coordinates using the [Vélib GBFS station database](https://www.velib-metropole.fr/donnees-open-data-gbfs-du-service-velib-metropole)
3. Fetches cycling routes from Google Maps Directions API (cached in `rides.json`)
4. Commits updated data

## Files

| File | Description |
|------|-------------|
| `index.html` | Self-contained map viewer (Leaflet + vanilla JS) |
| `rides.json` | All ride data, station lists per day, and route cache |
| `poll.py` | Hourly polling script |
| `stations.json` | Vélib station database (GBFS) |
| `.github/workflows/poll.yml` | Hourly cron workflow |

## License and code

Code is MIT licensed. Feel free to use the map as you wish, with or without attribution. Written by Claude Sonnet 4.6 and Claude Opus 4.6 (with prompts by me, Dominik Peters).