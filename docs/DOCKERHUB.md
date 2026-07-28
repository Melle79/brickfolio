# Brickfolio 🧱

Self-hosted PWA to scan, manage and value a **LEGO® collection** – built for a
whole family on one shared database, with an optional collector mode for
people who buy and sell at flea markets.

**Photo → recognition → collection.** Photograph a minifigure or set with your
phone, tap the match, done.

📖 **[Full documentation on GitHub](https://github.com/Melle79/brickfolio)** ·
🇩🇪 [Deutsches Handbuch](https://github.com/Melle79/brickfolio/blob/main/docs/HANDBUCH.md)

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

## Notes

Your collection stays on your server – there is no Brickfolio service in
between and no account to sign up for. Prices and catalogue search use your
own free BrickLink and Rebrickable keys.

LEGO® is a trademark of the LEGO Group, which does not sponsor, authorise or
endorse this project. Private hobby project, MIT licensed.
