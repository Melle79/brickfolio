# Finn's Brickfolio 🧱

*🇬🇧 English · [🇩🇪 Deutsch](README.md)*

[![Buy Me a Coffee](https://img.shields.io/badge/Buy%20Me%20a%20Coffee-support-ffdd00?logo=buymeacoffee&logoColor=black)](https://buymeacoffee.com/melle79)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

A self-hosted PWA to scan, manage and value a LEGO® collection – built for the
whole family on one shared database, with an optional **Collector-Pro mode**
for anyone who buys and sells at flea markets.

**Photo → recognition → collection.** Recognition runs on the free
[Brickognize API](https://brickognize.com); prices, set inventories and
metadata come from [BrickLink](https://www.bricklink.com) and
[Rebrickable](https://rebrickable.com) (your own API keys required, see below).

> 📖 The full **user manual** (German) lives at
> [`docs/HANDBUCH.md`](docs/HANDBUCH.md).

## Features

**Capture & manage**
- 📷 Scan minifigures and sets straight from the phone camera (candidate list
  with match score) or search by name/number – plain numbers are looked up as
  both a set *and* a figure automatically
- 📦 Quantities, condition (new/used), notes, image gallery, full-text search,
  sorting and type filter; optional **grid view** (two per row) for browsing
- 👥 **Add a set's figures with it**: when a set enters the collection, the app
  asks which of its minifigures are included (all, none or a selection, with
  their own condition) – without double-counting them in the total value
- 👥 Set linking: sets know their figures (“👥 3/4 ✔” completeness), figures
  show which of your sets they belong to; missing set figures move to the
  wishlist with a single tap

**Prices & value**
- 💶 BrickLink average prices (new/used) fetched automatically in the
  background, with a built-in **price-history log** and per-item chart
- 📊 **Stats tab**: key figures, overall value trend, split by type/condition,
  value by release year (tap a bar for the year’s details), Top 10

**Wishlist**
- ⭐ Save from any scan/search result, average-price widgets, “bought” hand-off
  into the collection incl. condition choice
- 🧩 Figures that belong to one of your sets and are still missing are flagged
  with “missing from your set” – a tap jumps straight to the set

**Collector-Pro mode** (a role the admin grants per user)
- 💰 Purchase price per entry – pre-filled with the BrickLink average of the
  capture day (⚙️) or entered manually (✏️), with profit/loss display
- 🛒 **Shopping lists** for the flea market: fill by scanning, live market
  value, purchase price per item, a **bundle offer** with proportional
  distribution by market value and a 60 % price suggestion
- 📋 **Sell list**: every duplicate with its giveaway quantity and sale value –
  figures needed for your own sets stay reserved, everything else keeps one
  copy for you
- 🧩 **Missing set figures**: across all your sets, which minifigures are still
  missing (count, sets, estimated cost) – add them to the wishlist one by one
  or all at once, export as CSV or print
- 🗒 When receiving from a shopping list, the **list name is written into the
  notes** of the collection entry (origin stays traceable)
- 📈 Extra stats: total paid, profit, best value gains

**Family & operations**
- 🔐 Multi-user with token login (PBKDF2-hashed passwords), admin and pro
  roles, self-service password/name change
- 💾 Full **backup** as JSON (download & restore), CSV export and print-ready
  lists
- 🏷 Configurable **display name** in logo and title (default “Finn”); ideal
  when several family members each run their own instance
- 🌌 Two **themes** to choose from (More → Design): light “Classic” and dark
  “Galaxy” with a starfield – the choice is per device
- 📲 Installable as a PWA, offline shell, no cloud – everything stays on your
  own server

## Screenshots

| Scan | Collection |
|:---:|:---:|
| <img src="docs/screenshots/scannen.png" width="260" alt="Scan"> | <img src="docs/screenshots/sammlung.png" width="260" alt="Collection"> |
| **Stats** | **Shopping list (flea-market mode)** |
| <img src="docs/screenshots/statistik.png" width="260" alt="Stats"> | <img src="docs/screenshots/einkaufsliste.png" width="260" alt="Shopping list"> |

*(Screenshots with demo data)*

## Quick start (Docker)

```bash
git clone https://github.com/Melle79/brickfolio.git
cd brickfolio
cp docker-compose.example.yml docker-compose.yml
docker compose up -d --build
```

Open `http://<server>:8300` – on first visit the app walks you through
**initial setup** (create the admin account). The database is stored
persistently at `./data/brickfolio.db`.

**Without git** (e.g. on a Synology NAS where git is usually missing) – grab
the latest release as an archive:

```bash
mkdir brickfolio && cd brickfolio
curl -sL https://github.com/Melle79/brickfolio/archive/refs/heads/main.tar.gz | tar xz --strip-components=1
cp docker-compose.example.yml docker-compose.yml
docker compose up -d --build
```

### Synology NAS

Create a folder at `/volume1/docker/brickfolio` and run the commands over SSH
with `sudo` (for the curl variant use `sudo sh -c 'curl … | tar …'` so the
whole pipe runs with the right permissions).

## Configuration

| Variable | Required | Description |
|---|---|---|
| `ADMIN_USER` / `ADMIN_PASSWORD` | no | Optional: create the admin automatically (otherwise via browser setup) |
| `DB_PATH` | no | Path to the SQLite file (container default: `/data/brickfolio.db`) |
| `BL_CONSUMER_KEY` / `BL_CONSUMER_SECRET` / `BL_TOKEN` / `BL_TOKEN_SECRET` | no | BrickLink Store API for prices & set inventories ([request a key](https://www.bricklink.com/v2/api/register_consumer.page)) |
| `BACKUP_KEEP` | no | Keep this many automatic daily backups (default 14, 0 = off) |
| `REBRICKABLE_KEY` | no | Rebrickable API for name search ([create a key](https://rebrickable.com/api/)) |
| `BRICKFOLIO_NAME` | no | Display name in logo/title (default “Finn”); also settable in-app |

All API keys can alternatively be stored **in the app** (More → API keys,
admin only) – environment variables serve as a fallback.

## Permissions overview

| Action | Default | Collector-Pro | Admin |
|---|:-:|:-:|:-:|
| Scan, collection, wishlist, stats | ✔ | ✔ | ✔ |
| See shopping lists & mark an item “received” | ✔¹ | ✔ | ✔¹ |
| Create/fill/archive lists, bundle offer, sell list | – | ✔ | – |
| See purchase prices & profit | – | ✔ | – |
| Users, roles, API keys, backup | – | – | ✔ |

¹ The tab only appears when at least one active list exists.
Roles combine (the admin can grant themselves the pro role).

## Updates & backup

- Deploy a new version: replace the files, then
  `docker compose up -d --build` – database migrations run automatically.
  Easier: run `sudo bash update.sh` in the project folder.

### Updating from inside the app (optional)

**Entirely optional** – without setup nothing changes and updates keep working
via `update.sh` over SSH. The button only appears once the helper below is in
place; until then the app just points to it.

**How it works.** The app does **not** run the update itself – it can’t, since
it lives inside the container. It only writes `data/update-requested.json`. A
small script on the server picks that up and runs `update.sh`. That way the app
needs **no Docker access** – handing the socket to a container is effectively
root on the host.

#### Setup

Run `update-watch.sh` regularly. **Once a minute is plenty** – the update
itself takes one to three minutes anyway.

**Synology (DSM):** Control Panel → Task Scheduler → Create → Scheduled Task →
User-defined script

| Tab | Setting |
| --- | --- |
| General | User: **`root`** (otherwise the script may not run `docker compose`) |
| Schedule | Daily · start `00:00` · “Continue running within the same day” ✔ · repeat **every minute** · last run time: **`23:59`** |
| Task Settings | Command: `sh /path/to/brickfolio/update-watch.sh` |

> ⚠️ “Last run time” defaults to `00:59` – the task would then only run during
> the first hour of the day. Set it to `23:59`.

**Linux with cron:** `* * * * * sh /path/to/brickfolio/update-watch.sh`

#### Multiple instances

Running several Brickfolios (each in its own folder with its own
`docker-compose.yml`)? **One** task with multiple lines is enough:

```sh
sh /volume1/docker/brickfolio/update-watch.sh
sh /volume1/docker/nerdfan/update-watch.sh
```

They stay independent – each has its own marker in its own `data` folder, so
updating one leaves the other alone.

#### Flow

The admin picks now / 1 min / 5 min → every signed-in browser shows a countdown
(“please finish your edits”), then a lock screen. Once the server is back, the
browsers reload themselves. While the countdown runs, the admin can cancel.

- The helper touches `data/update-watch-alive` on every run. That is how the
  app knows it is set up – if the heartbeat is older than five minutes, the
  update is not offered at all.
- Log of every run: `data/update-watch.log`.
- Backup: in-app under More → Backup (JSON with all data incl. users and
  price history) **or** simply copy `data/brickfolio.db`.

## Tech

FastAPI + SQLite (no ORM) · Vanilla-JS PWA (no build step) ·
Docker deployment · APIs: Brickognize, BrickLink Store API (OAuth1),
Rebrickable.

## Legal

LEGO® is a trademark of the LEGO Group, which does not sponsor, authorise or
endorse this project. BrickLink, Rebrickable and Brickognize are trademarks of
their respective owners; their APIs are subject to their respective terms of
use. This is a private hobby project with no commercial intent.

Data and images come from Rebrickable (catalogue search), BrickLink (prices,
set contents, images) and Brickognize (image recognition – taking a photo
sends it there). The same notes are shown in the app under
**More → Sources & legal**.

The **Nunito** typeface (SIL Open Font License 1.1, licence text in
`frontend/fonts/OFL.txt`) is served locally. No visitor data is sent to font
CDNs, and the app stays fully usable without an internet connection.

## Support

Brickfolio is a private hobby project and free to use. If you like it and want
to support development, I'd be happy about a coffee ☕

<a href="https://buymeacoffee.com/melle79"><img src="https://img.shields.io/badge/Buy%20Me%20a%20Coffee-melle79-ffdd00?logo=buymeacoffee&logoColor=black" alt="Buy Me a Coffee"></a>

## License

[MIT](LICENSE)
