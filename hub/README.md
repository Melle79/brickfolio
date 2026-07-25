# Brickfolio-Hub

Dünne Austausch-Schicht, damit getrennte Brickfolio-Instanzen **tauschen und
kommunizieren** können, ohne sich gegenseitig erreichen zu müssen. Läuft als
**Cloudflare Worker + D1** auf einer Subdomain (z. B. `hub.brickfolio.cc`).

## Warum ein Hub (und kein p2p)

Instanzen sitzen hinter Tunnel/Access und sind von außen nicht direkt
ansprechbar. Sie reden aber **ausgehend** problemlos mit dem Hub. Beide Seiten
pushen/ziehen nur beim immer-erreichbaren Hub – Nachrichten liegen dort, bis der
andere sie abholt. Kein „beide müssen gleichzeitig online sein".

```
Instanz A ──(Bearer-Token)──▶  HUB (Worker + D1)  ◀──(Bearer-Token)── Instanz B
   push eigene Angebote          Identitäten            push eigene Angebote
   zieh fremde Angebote          Angebote               zieh fremde Angebote
                                 Postfach (später)
```

## Grundsätze

- **Dünn:** Der Hub speichert **nur** freigegebene Angebote, Identitäten und
  (später) das Postfach. **Keine** Sammlungen, keine Bilder-Blobs.
- **Opt-in:** Nichts verlässt eine Instanz automatisch. Nur der bewusst
  freigegebene „Abgebbar"-Bestand wird gepusht.
- **Token bleibt server-seitig:** Die Instanz spricht server-zu-server mit dem
  Hub. Der Token liegt in der Instanz-DB, **nie im Browser**. Deshalb kein CORS.
- **Kein Cloudflare Access vor dem Hub:** Access ist Browser-SSO und für
  Maschine-zu-Maschine unpraktisch. Der Hub authentifiziert selbst per Token.

## Identität & Beitritt

- **Ein Hub-Mitglied = eine Instanz** (ein Brickfolio-Deployment), mit
  Anzeigename. Trades laufen zwischen Instanzen.
- **Einladungs-Modell (Freundeskreis):** Ein Admin erzeugt einen Einladungscode,
  eine neue Instanz löst ihn einmalig ein und bekommt ihren **Instanz-Token**.
- **Erststart (Bootstrap):** Der allererste Admin wird mit dem
  `HUB_BOOTSTRAP_SECRET` angelegt (kein Code nötig).

## Datenmodell (D1)

Siehe [`schema.sql`](schema.sql): `members`, `invites`, `offers`, `messages`.
`offers` wird pro Instanz beim Sync **komplett ersetzt** (delete-all + insert),
damit entfernte Angebote auch wieder verschwinden.

## API (v1)

Alle Antworten JSON. Auth via `Authorization: Bearer <token>`, außer
`/v1/health` und `/v1/register`.

| Methode & Pfad | Auth | Zweck |
|---|---|---|
| `GET /v1/health` | – | Lebt der Hub? |
| `POST /v1/register` | – | Beitritt: `{invite_code, display_name}` **oder** Bootstrap `{bootstrap_secret, display_name}` → gibt **einmalig** `{member_id, token}` |
| `GET /v1/me` | ✓ | Eigene Member-Infos |
| `POST /v1/token/rotate` | ✓ | Token neu erzeugen (alter wird ungültig) |
| `PUT /v1/offers` | ✓ | Eigene Angebote **ersetzen**: `{offers:[{item_id,item_type,name,img_url,bricklink_url,condition,qty,note}]}` |
| `GET /v1/offers` | ✓ | Angebote **anderer** (`?mine=1` für eigene, `?member=`, `?q=`) |
| `GET /v1/members` | ✓ | Mitgliederliste + Angebotszahl |
| `POST /v1/invites` | ✓ (Admin) | Einladungscode erzeugen `{note?, expires_in_days?}` → **einmalig** `{invite_code}` |

## Einrichtung

Voraussetzung: Node + `npx wrangler`, in Cloudflare eingeloggt (`wrangler login`).

```bash
cd hub
npm install

# 1) D1 anlegen und die ausgegebene database_id in wrangler.toml eintragen
npx wrangler d1 create brickfolio-hub

# 2) Schema einspielen (remote = die echte D1)
npx wrangler d1 execute brickfolio-hub --remote --file=schema.sql

# 3) Bootstrap-Secret setzen (für den ersten Admin)
npx wrangler secret put HUB_BOOTSTRAP_SECRET

# 4) In wrangler.toml die [[routes]] auf hub.brickfolio.cc aktivieren, dann:
npx wrangler deploy
```

Ersten Admin anlegen (Token nur einmal sichtbar – sicher speichern):

```bash
curl -s https://hub.brickfolio.cc/v1/register \
  -H 'content-type: application/json' \
  -d '{"bootstrap_secret":"<dein-secret>","display_name":"Finn"}'
```

## Lokal testen (ohne Cloudflare-Konto)

`wrangler dev` startet den Worker mit lokaler D1 (SQLite/Miniflare):

```bash
cd hub
npx wrangler d1 execute brickfolio-hub --local --file=schema.sql
npx wrangler dev            # Worker auf http://localhost:8787
```

## Nächste Schritte (App-Seite)

1. **Freigabecenter** in Brickfolio: Hub-URL + Einladungscode eingeben, Token
   server-seitig speichern; auswählen, was aus „Abgebbar" veröffentlicht wird;
   „Jetzt veröffentlichen" → `PUT /v1/offers`.
2. **Angebots-Ansicht:** „Das haben deine Freunde" → `GET /v1/offers`.
3. **Postfach:** Anfragen/Nachrichten (`messages`).
4. **Matching:** eigene Suchliste ↔ fremde Angebote.
