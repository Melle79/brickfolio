# Brickfolio 🧱

Self-hosted PWA to scan, manage and value a **LEGO® collection** – built for a
whole family on one shared database, with an optional collector mode for
people who buy and sell at flea markets.

**Photo → recognition → collection.** Photograph a minifigure or set with your
phone, tap the match, done.

[![License: MIT](https://img.shields.io/badge/license-MIT-blue)](https://github.com/Melle79/brickfolio/blob/main/LICENSE)
[![Platforms](https://img.shields.io/badge/arch-amd64%20%7C%20arm64-informational)](https://hub.docker.com/r/melle79/brickfolio/tags)
[![GitHub](https://img.shields.io/badge/source-GitHub-black?logo=github)](https://github.com/Melle79/brickfolio)

📖 **[Full documentation on GitHub](https://github.com/Melle79/brickfolio)** ·
🇩🇪 [Deutsches Handbuch](https://github.com/Melle79/brickfolio/blob/main/docs/HANDBUCH.md)

| Scan | Collection | Statistics |
|---|---|---|
| ![Scanning](https://raw.githubusercontent.com/Melle79/brickfolio/main/docs/screenshots/scannen.png) | ![Collection](https://raw.githubusercontent.com/Melle79/brickfolio/main/docs/screenshots/sammlung.png) | ![Statistics](https://raw.githubusercontent.com/Melle79/brickfolio/main/docs/screenshots/statistik.png) |

## Quick start

```yaml
services:
  brickfolio:
    image: melle79/brickfolio:latest
    container_name: brickfolio
    restart: unless-stopped
    ports:
      - "8300:8300"
    volumes:
      - ./data:/data
```

```bash
docker compose up -d
```

Open `http://<server>:8300` – a **setup wizard** walks you through the admin
account, the display name and the API keys, and every step can be skipped.

## What you get

- 📷 **Camera scanning** via the free [Brickognize](https://brickognize.com)
  API, plus catalogue search by name or number
- 💶 **BrickLink average prices** with your own price history and per-item
  charts, selectable price region
- ⭐ Wishlist, 🛒 shopping lists for flea markets with proportional offer
  splitting, 📋 duplicates/sell list, 📊 statistics
- 👥 **Multi-user** with admin and collector-pro roles, JSON backup, CSV
  export, print lists
- 🤝 Optional **trading network**: several instances connect through a small
  hub to swap items, with end-to-end encrypted messages
- 📲 Installable as a PWA, three themes, works on phone and desktop

## Configuration

Everything is optional – the setup wizard asks for the keys, or use
environment variables:

| Variable | Purpose |
|---|---|
| `ADMIN_USER` / `ADMIN_PASSWORD` | Create the admin account unattended |
| `REBRICKABLE_KEY` | Catalogue search by name |
| `BL_CONSUMER_KEY` / `BL_CONSUMER_SECRET` / `BL_TOKEN` / `BL_TOKEN_SECRET` | BrickLink prices and set contents |
| `BACKUP_KEEP` | How many daily backups to keep (default 14) |

The database lives in `/data` – that is the only volume that matters.

**Architectures:** `linux/amd64` and `linux/arm64`.
Also available as `ghcr.io/melle79/brickfolio`.

## Tags

| Tag | What it is |
|---|---|
| `latest` | The newest release. Pre-releases are excluded on purpose. |
| `2.79.2`, `2.79`, `2` | Pinned to a release, down to the level you want. |
| `main` | Follows the development branch – newest, least tested. |

## Notes

Your collection stays on your server – there is no Brickfolio service in
between and no account to sign up for. Prices and catalogue search use your
own free BrickLink and Rebrickable keys.

LEGO® is a trademark of the LEGO Group, which does not sponsor, authorise or
endorse this project. Private hobby project, MIT licensed.
