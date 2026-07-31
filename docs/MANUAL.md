# Finn's Brickfolio – The Manual

*July 2026 · [🇩🇪 Deutsche Fassung](HANDBUCH.md)*

Brickfolio is a self-hosted Progressive Web App (PWA) for scanning, managing
and valuing a LEGO® collection. This manual explains every feature – from the
first start to a day at the flea market.

## Contents

1. [About Brickfolio](#1-about-brickfolio)
2. [Installation & first setup](#2-installation--first-setup)
3. [Users & roles](#3-users--roles)
4. [Scanning & adding](#4-scanning--adding)
5. [The collection](#5-the-collection)
6. [The wishlist](#6-the-wishlist)
7. [Shopping lists – flea-market mode](#7-shopping-lists--flea-market-mode)
8. [The sell list (duplicates)](#8-the-sell-list-duplicates)
9. [The statistics tab](#9-the-statistics-tab)
10. [CSV import, export & printing](#10-csv-import-export--printing)
11. [Backup, restore & updates](#11-backup-restore--updates)
12. [The trading network](#12-the-trading-network)
13. [The price automation in detail](#13-the-price-automation-in-detail)
14. [Troubleshooting](#14-troubleshooting)
15. [FAQ](#15-faq)
16. [Appendix](#16-appendix)

---

## 1. About Brickfolio

Brickfolio follows three basic ideas:

**Adding something should take seconds.** Photograph a figure or a set with
your phone, tap the match, pick the condition – done. Recognition is handled
by the free [Brickognize API](https://brickognize.com); names and metadata
come from Rebrickable and BrickLink.

**The collection should know what it is worth.** BrickLink average prices are
fetched automatically and recorded continuously – from that come price
histories per item and the value trend of the whole collection.

**Your data stays with you.** Everything runs in a single Docker container on
your own server (FastAPI + SQLite). There is no Brickfolio service in between
that you would have to sign up for, and your collection lives nowhere else.
Several family members share one database, each with their own login.

The app only reaches outside where it has to: for scanning (Brickognize), for
search by name (Rebrickable) and for prices and set contents (BrickLink). The
latter two need your own free access – see 2.4. Without them everything else
keeps working.

**One point that is easily missed: the images.** The database holds only the
*address* of each item's catalogue picture. It used to be fetched by **your
browser** directly from `img.bricklink.com`, `cdn.rebrickable.com` or – for
anything scanned – `storage.googleapis.com`, where Brickognize keeps its
thumbnails. Nothing from your collection went out, but the image address names
the part number, and every time you browsed, such a request went off.

**Since 1.61.0 the pictures live on your instance.** When an item is added the
server fetches its picture once, scales it down to 400 pixels and stores it
next to the database (`data/catalog/`). After that the browser only ever asks
**your own instance** – nothing goes outside any more. Older items are caught
up by **More → 🖼 Images on your instance**; the card says how many are
missing and works through them in portions.

The fetch can only ever reach the four catalogue hosts – it is no route to the
outside, and dedicated tests watch over that. The file name is derived from the
image address **and your instance's key**; without it nobody can work out from
a part number whether that picture is stored here.

Roughly 10–25 KB per item, so 1000 items are about 15–25 MB on disk. They are
**not** part of the JSON backup – that stays small, and the button fetches lost
pictures again at any time.

If you like, you can additionally connect your instance to the **trading
network** (chapter 12) – then several households can reach each other. Even
then the collection stays at home: only what someone explicitly offers for
trade goes out, and messages are end-to-end encrypted.

**The technology in one sentence:** Python backend (FastAPI) with an SQLite
database, vanilla-JS frontend without a build step, installable as a PWA on
your home screen.

---

## 2. Installation & first setup

### 2.1 Requirements

- A server with Docker and Docker Compose (tested on Synology DSM among
  others); 512 MB of RAM is enough.
- For prices and the like: free API access at BrickLink and Rebrickable
  (see 2.4 – the app also works without, then without prices and search by
  name).

### 2.2 Installation

There is a ready-made image – nothing to build, no source code needed:

```bash
mkdir brickfolio && cd brickfolio
curl -sLo docker-compose.yml https://raw.githubusercontent.com/Melle79/brickfolio/main/docker-compose.example.yml
docker compose up -d
```

The app is then reachable at `http://<server>:8300`. The database lives
persistently at `./data/brickfolio.db` – that folder survives updates and
container rebuilds.

The image exists on two registries (identical in content, pick one):
`ghcr.io/melle79/brickfolio:latest` and `melle79/brickfolio:latest`. It is
built for **amd64** (Intel/AMD, most NAS boxes) and **arm64** (Raspberry Pi,
ARM NAS, Apple Silicon). Very old 32-bit ARM devices are not supported.

**Without a shell**, e.g. on a Synology: the Container Manager interface takes
the same YAML. Step by step in [`SYNOLOGY.md`](SYNOLOGY.md) (in German); for
other vendors the README lists where the respective dialog sits.

**Building it yourself** (only needed for your own changes): fetch the source
and replace the `image: …` line in `docker-compose.yml` with `build: .`, then
`docker compose up -d --build`.

**Changing the port / running several instances:** the reachable port is the
*first* number in the `ports` mapping of `docker-compose.yml` – `"8301:8300"`
makes the app available on port 8301 (the second number always stays 8300).
That is also how you run several Brickfolio instances side by side, e.g. for
separate collections or a test installation: its own folder, its own
`container_name`, its own port – every instance has its own `data/` folder and
therefore its own database.

**Synology note:** create the folder under `/volume1/docker/brickfolio` and
run all commands over SSH with `sudo`.

### 2.3 First start: the setup wizard

On the first visit in the browser you pick a username and password for the
**admin account**. Right above those fields you also choose the **language**
(German or English) – the choice goes into the profile of the account you are
about to create, so it applies on every device.

After that you are signed in, and a wizard walks you through the rest in seven
steps:

1. **Display name** – the name in the logo and window title ("Finn's
   Brickfolio")
2. **Price region and currency** – which market the average prices come from
   and in which currency; preselected is what matches your browser's language
   settings (see chapter 13.1)
3. **Rebrickable key** – for search by name, with a direct link
4. **BrickLink access** – the four values for prices and set contents
5. **Test the connection** – a real test call to both services, so a mixed-up
   key shows up now and not at your first scan
6. **Trading network** – if somebody invited you (see chapter 12)
7. **Done**

**Every step can be skipped**, and at the bottom there is "Finish the wizard
and get started". Without keys everything works except prices, set contents
and search by name – **scanning needs no key at all**. Anything can be added
later under *More → API keys*.

The wizard runs exactly once, right after the admin account is created.

*For unattended setups:* if the environment variables
`ADMIN_USER`/`ADMIN_PASSWORD` are set, Brickfolio creates the admin on the
very first start; the wizard is then skipped and the keys come either from
environment variables or from *More → API keys*.

### 2.4 Setting up API keys (admin)

Under **More → API keys** (only visible to admins):

**BrickLink** – provides average prices, release years and set contents:

1. You need a BrickLink account **with an opened store** – the store API is
   only open to sellers. The store does not have to sell anything, it just
   has to exist (BrickLink: *My Store*).
2. On [API → Register Consumer](https://www.bricklink.com/v2/api/register_consumer.page)
   accept the terms and create an **access token**. Fill **both IP fields**
   (IP address *and* mask) with `0.0.0.0` – that allows access from any
   address.
3. Copy the four values – *Consumer Key*, *Consumer Secret*, *Token*,
   *Token Secret* – into the four fields in the app and save.

**Rebrickable** – provides search by name:

1. Create a free account on rebrickable.com.
2. Under [Account → API](https://rebrickable.com/api/) create a key and enter
   it in the *Rebrickable Key* field.

Finally press **"Test connection"** – the app checks both and reports the
result. The same instructions live inside the app too: ❓ button at the top
right → "Getting API keys". Stored keys are shown masked; leaving a field
empty when saving keeps the existing value. Alternatively all keys can be set
as environment variables (see README); the settings in the app take
precedence.

### 2.5 Onto your phone as an app (PWA)

If Brickfolio is still running in the browser on a phone, the scan page shows
the card **"📲 Add to the home screen"** at the top. What it offers depends on
the device:

- **Android and other Chromium browsers**: "Add it now" triggers the
  installation directly.
- **iPhone and iPad**: Safari has no button for this – the card explains the
  route via *Share → "Add to Home Screen"*.
- **Over a plain `http` address on the home network** no browser allows
  adding it. The card then says exactly that and points to *More → External
  access* (2.7), which sets up an encrypted address.

**Pull down to reload.** Started from the home screen there is no address
bar and therefore no reload button; on iOS there is no gesture for it either.
So Brickfolio brings its own: at the top of the list, pull down until the
brick turns green, then let go. In the browser it stays off – the address bar
already does that.

As soon as the app runs from the home screen the card disappears by itself –
it detects the display mode. "Don't show again" hides it permanently, per
device.

Once installed, Brickfolio starts like a native app in full screen –
including camera access for scanning.

### 2.6 Getting your bearings: header and the More tab

Two companions sit in the header: the **❓ button** (top right) opens the help
as a popup – from any tab, with instructions for every feature. And **your own
name** next to it is tappable: behind it is the **profile popup** with change
display name, change password and sign out.

**💬 Unread messages.** If something is waiting in the trade network, a mark
with the number of unread messages appears to the left – visible from every
tab. Tapping it goes straight to *Trade → My conversations*. If nothing is
open, there is no mark either. When the app opens, Brickfolio asks the hub
once so the number is right immediately instead of after the next cycle.

> **Phone or computer?** The navigation sits **at the bottom on a phone** and
> **as a sidebar on the left on wide screens**. There the app uses the space:
> key figures side by side, and four to five cards per row in the collection
> grid. It is the same app – it just arranges itself according to screen
> width, without you switching anything.

The **More** tab is arranged in four groups, sorted by **who it concerns**.
Cards fold open and shut by tapping the heading; the app remembers the state.
If a whole group is empty for your role, its heading disappears too – so a
regular user only sees the first group and the sources at the very bottom.

| Group | Card | visible to |
|---|---|---|
| 🙋 **For you** | 🌐 Language | everyone |
| | 🎨 Design | everyone |
| | ↕️ Collection sort order | everyone |
| | 📤 Export & print | everyone |
| | 💼 Collector-Pro (offer suggestion, CSV import) | Collector-Pro |
| | 📈 Price log | Collector-Pro |
| 🏠 **This instance** | 🏷 Display name | Admin |
| | 👥 Manage users | Admin |
| | 🔑 API keys | Admin |
| | 🌍 Price region & currency | Admin |
| | 🖼 Images on your instance | Admin |
| 🌐 **Outward** | 🌐 External access | Admin |
| | 🤝 Trading network (connect/disconnect) | Admin |
| 🛠 **Maintenance** | 💾 Backup | Admin |
| | 🔄 Version & updates | Admin |
| | 🐞 Error report | Admin |
| *(no group)* | ℹ️ Sources & legal | everyone |

**🌐 Language** switches between German and English. The choice is stored in
your profile and therefore applies on every device; without one the app
follows your browser language. Switching happens instantly – nothing you have
typed is lost.

**🎨 Design** offers three looks: **Classic** (light, LEGO colours),
**Galaxy** (dark, with a starfield and glowing accents) and **Nova** (a modern
glass design – deep dark, shimmering blue background, translucent surfaces and
a blue accent). The choice is **stored in your profile** and therefore applies
**on every device** once you are signed in. The admin additionally sees a
**star** on every design: ⭐ marks the **default design of the instance**;
tapping the star of another design makes that one the default. It applies to
the login screen and to users who have not chosen for themselves (the star
does not change your own choice).

**ℹ️ Sources & legal** names where data and images come from (Rebrickable,
BrickLink, Brickognize), points out that taking a photo transmits it for
recognition, and lists trademark, font and program licences.

### 2.7 Reaching it from anywhere (Cloudflare Tunnel)

By default Brickfolio only runs on your **home network**. If you also want
access from elsewhere (phone on mobile data, another location), you should
**not open ports on your router** – that exposes the server to the whole
internet. The recommendation instead is a **Cloudflare Tunnel**: safer,
simpler and free.

**Why a Cloudflare Tunnel**

- **No open port.** The tunnel builds an *outgoing* connection to Cloudflare –
  nothing has to be forwarded inwards on the router or NAS. That shrinks the
  attack surface enormously.
- **HTTPS included.** The app is reachable encrypted under its own
  (sub)domain, without you maintaining certificates.
- **Works behind CGNAT** and without a fixed public IP – important on many
  cable and mobile connections.

**Requirement:** a free Cloudflare account and a domain managed at Cloudflare
(register a cheap one or move an existing one).

**Recommended installation** – `cloudflared` as a second container right next
to Brickfolio, driven by a tunnel token:

1. In the **Cloudflare Zero Trust** dashboard under *Networks → Tunnels*
   create a tunnel and copy the **token** shown.
2. On the tunnel enter a *Public Hostname*, e.g.
   `brickfolio.your-domain.com`, with the service
   **`http://brickfolio:8300`** (the container name and port from above).
3. Add this next to the `brickfolio` service in `docker-compose.yml`:

   ```yaml
     cloudflared:
       image: cloudflare/cloudflared:latest
       container_name: brickfolio-tunnel
       restart: unless-stopped
       command: tunnel run
       environment:
         TUNNEL_TOKEN: "put-the-token-here"
   ```

   Both containers sit on the same compose network, so `cloudflared` reaches
   the app at `http://brickfolio:8300`. Then `docker compose up -d`.

Brickfolio is then reachable encrypted from anywhere at
`https://brickfolio.your-domain.com` – with no port forwarding at all. Over
that address it can also be put on your phone as a PWA (see 2.5).

> **An extra lock (recommended):** in the Zero Trust dashboard you can put an
> **access policy** in front of the app – for example sign-in by one-time
> email code, or a restriction to certain addresses. Then only people
> Cloudflare has confirmed reach the login page at all. For your own family
> the normal Brickfolio login is often enough; the access policy is the second
> door for anyone who wants to be certain.

**Several instances** (e.g. one per family member): simply create several
*public hostnames* pointing at the respective container ports – a single
`cloudflared` container is enough for that.

### 2.8 How the app is secured – and what it is not built for

Brickfolio is built for the **home network**. If you forward a port on your
router, you should know what protects you and what does not.

**What is there:**

- **Every data access requires a login.** Only the start page, signing in,
  the initial setup and the image files themselves are open (and their names
  are random and cannot be guessed).
- **Passwords** are stored as PBKDF2-SHA256 with 200,000 rounds and a
  per-user salt – not in plain text, not as a simple hash.
- **Password guessing is throttled**: ten failed attempts per account and per
  origin, then a 15-minute pause. The correct password does not count during
  that time either – otherwise someone who just guessed it would slip
  through. A successful login resets the counters.
- **Security headers**: the page cannot be put inside someone else's frame,
  the browser must not guess file types, and a content policy only allows
  scripts from the app itself.
- **Uploaded images** are re-encoded – that strips EXIF data (GPS from phone
  photos, for instance) and makes sure nothing other than an image is stored.
- **Roles**: purchase prices, list management, users, keys and backup all sit
  behind pro or admin rights. **Rights are read fresh from the database on
  every request**, not taken from the session token: if an admin removes
  someone's rights or deletes the account, that takes effect immediately and
  not only when the session expires.
- **Changing a password ends all previous sessions** (since v1.67.0) – on
  every device. If you change your password because a device went missing, you
  really do lock it out; your own device gets a fresh session and stays signed
  in. The same applies when an admin resets a password or removes a second
  factor.
- **Secrets are stripped from every error message** before it is stored or
  sent as a GitHub issue – API keys, GitHub token, hub access, the private hub
  key and the push key. A test fires as soon as a new setting appears that
  nobody has classified as secret or public.
- **`latest` means trusting the registry.** With `:latest` every update pulls
  the newest state from there – even if that account ever fell into the wrong
  hands. If you would rather not, pin a **fixed version**
  (`image: ghcr.io/melle79/brickfolio:1.67.0`). Then only what you picked runs.
  > **But:** a fixed version number only fixes the *name*. Whoever controls
  > the registry could serve something else under `1.67.0` just as under
  > `latest`. Real protection comes only from a **digest**
  > (`image: ghcr.io/melle79/brickfolio@sha256:…`) – it describes the content
  > itself and cannot be re-pointed. The release page or `docker image
  > inspect` shows the digest.
  >
  > **The price either way:** the update button in the app no longer does anything.
  > With a fixed version `docker compose pull` fetches the same state, the
  > container restarts and shows the same version. Updating then means editing
  > the line in `docker-compose.yml` and running `docker compose up -d`. The
  > app still reports that a new version is available – that is then a hint,
  > not an instruction for the button.

**What is missing – and why a port forward is still a bad idea:**

- **No encryption.** The app speaks `http`. Through a port forward, the
  password and the session token would travel the internet **in the clear**.
  That is the most serious point.
- **Passwords may be short** (at least eight characters since v1.57.0, four
  before that). Fine at home, thin for the open internet.
- **No second factor**, no sign-in through an external provider.
- **Sessions last 90 days** and live in browser storage.

**The recommendation** therefore stays the **Cloudflare Tunnel** (2.7): it
brings encryption, opens no port, and with an access policy there is even a
second door in front. If you want a port forward anyway, at the very least
use a long, unique password and restrict access to known addresses.

---

## 3. Users & roles

Brickfolio knows three levels, which can be combined:

| Action | Standard | Collector-Pro 💼 | Admin 🔧 |
|---|:-:|:-:|:-:|
| Scanning, collection, lists (wishes), statistics | ✔ | ✔ | ✔ |
| See shopping lists, book items in as "got it" | ✔¹ | ✔ | ✔¹ |
| Create/fill/archive lists, bundle offer | – | ✔ | – |
| See purchase prices & profit, sell list, CSV import | – | ✔ | – |
| Users, roles, API keys, backup | – | – | ✔ |

¹ The Lists tab only appears for standard users when at least one active list
exists.

**Creating a user (admin):** More → 👥 Manage users → name + password →
"Create user". Every user changes their own password and display name by
**tapping their name at the top right** (profile popup); the admin can reset
passwords and remove users.

**Granting roles:** in the user list the **Admin** button makes a user another
admin (👑) or takes the rights away again – but the **last** admin always
stays an admin, so nobody can lock themselves out. The **Pro** button toggles
Collector-Pro mode.

**Granting the Collector-Pro role (admin):** tap the **"Pro"** button in the
user list – it turns green ("Pro ✔"). The role takes effect immediately,
without signing in again; tapping it once more removes it. A typical family
setup: one parent is admin + pro, the child manages their collection with a
standard account.

**Worth knowing:** purchase prices are tracked in the background for *all*
entries – anyone who gets the pro role later sees complete data
retroactively.

### 3.1 Two-factor login (optional, per user)

If you like, you can protect your account additionally with a **one-time code
from an authenticator app** (Aegis, 1Password, Google Authenticator …). It is
the most sensible addition as soon as the app is reachable from outside.

**Turning it on** under *Profile* (tap your name at the top right) → **🔐
Two-factor login**:

1. Enter your password, "Set up" – a **QR code** appears; if you cannot scan,
   type in the key shown below it.
2. Enter the six-digit code from the app and press "Turn on". Only this step
   activates the protection – so nobody can lock themselves out with a key
   that was transferred incorrectly.
3. **Eight recovery codes** appear. They are shown **only this once**:
   afterwards the database holds nothing but their checksums. Print them or
   put them in your password manager.

**Signing in** then happens in two steps: first the password, then the code.
If you do not have your phone at hand, enter a **recovery code** instead of
the six digits – each works exactly once, and the app tells you how many are
left.

**Turning it off** requires the password *and* a valid code.

> **Phone lost and no recovery codes left?** Then an **admin** removes the
> second factor in user management. Without that way out, a lost device would
> mean a lost account. The last admin should therefore keep their recovery
> codes especially carefully.

**Worth knowing:**

- A code works **only once**. Someone reading it over your shoulder cannot
  reuse it within the same half minute.
- A clock difference of half a minute is allowed for. If the app stubbornly
  says "code does not match", it is usually the **phone's clock** that is off.
- The second step is throttled against guessing too (see 2.8).
- The app computes the codes according to RFC 6238 – the same procedure as
  every common authenticator app.

---

## 4. Scanning & adding

### 4.1 With the camera

In the **Scan** tab tap **"Photograph a figure or set"** and shoot the figure
or set filling as much of the frame as possible, in good light. On a computer
you can also **drag and drop** an image onto the scan area or paste a
**screenshot with Ctrl/Cmd+V**. The app shows a list of candidates with match
probability, image, number and – depending on the data – year, average prices
and ownership hints.

**Tips for good hit rates:** a plain background, the figure from the front, no
reflective packaging. For sets the box image or the built model works.

**Several figures in one picture.** Recognition looks for **one** object per
request – that is how the service is built. If several figures are on the
photo, it picks one. So that you can see which, the preview frames the
recognised figure in **green**.

So that all of them work in one go anyway, the app separates the figures
**itself**: **🔎 Recognise all figures** measures how much structure sits in
each image column. Where a figure stands, brightness changes densely –
helmet, arms, belt; in the gap next to it lies a calm surface. The cuts go
into the gaps, and each strip is sent to recognition on its own. The figures
found are framed and numbered, and below each gets its own card with
**＋ To the collection**.

This also copes with a **display case**: glass reflections, a bright shelf,
a blue-grey back wall and blue-grey figures – a colour comparison would find
nothing there, structure does.

> **If the number is wrong:** below the picture it says how many figures were
> found, with **−** and **＋** next to it. Change the number and the picture
> is divided into that many equal strips and everything is asked again. That
> helps with figures that touch – there is no gap to cut in.

**Where the automatic route reaches its limit.** It looks for **vertical
gaps**, so it is made for figures standing **side by side**: on a shelf, in a
display case, in a row on the table. If they lie criss-cross, stand staggered
behind one another or overlap, there is no clean gap to cut at.

For those cases there is the **reliable route**, and it is quick:

1. Drag a frame around one figure
2. **➕ Keep frame**
3. Repeat for every further figure – the kept ones stay, numbered
4. **🔎 Recognise all**

That works with any arrangement, because you set the boundaries instead of
the app having to guess them. **Discard** clears the kept frames again.

The single green frame labelled **"looked here"** is something else: it comes
from the recognition service and shows what it guessed at during the first
scan. As soon as numbered frames appear, it goes away.

That one always works: drag a **frame around one figure** with your finger
(or the mouse) and tap **🔍 Recognise this crop**. The cropping happens in
the browser, only the crop goes to the server.

### 4.2 By search (catalogue)

Below the camera area sits the text search. It understands:

- **Names** ("Shoretrooper", "TIE Striker") – via Rebrickable
- **Figure numbers** (`sw0815`, `col424`)
- **Set numbers** (`75154` or `75154-1`)
- **Plain numbers** are looked up on several tracks automatically – as a set
  *and* as a figure; the app shows what it finds.

The search starts **from three characters** – with a shorter input you get a
short hint instead of a request. The **type** (minifigure/part/set) sits right
next to the name field so you can search deliberately.

You get **10 hits per page**; below them it says "X of Y shown" plus a **Load
more results** button that appends ten more each time – so every match is
reachable.

**Detail view.** Tapping a hit – from the search **as well as from a scan** –
opens a popup with everything that is known: a large image, year, theme,
average prices new/used, a BrickLink link. For **minifigures** you can unfold
"Parts it contains" there: every part with number, quantity and **colour name**
– handy for judging an incomplete figure at a stall. The buttons for adding it
are the same as on the card.

### 4.3 Actions on every result card

- **＋ To the collection** – asks for the **condition** (used/new) and offers
  an optional **"Paid €"** field: if you already know what you paid, enter it
  right away (it lands as the purchase price in the collection). If the item
  already exists, its quantity goes up.
- **☆ Save** – puts it on the wishlist (a ⭐ badge appears).
- **🛒 List** *(pro only)* – puts it on a shopping list (see chapter 7): in the
  dialog optionally pick the **condition** first (used/new, used is
  preselected), then tap the list – or create one right at the stall with
  **"＋ New list"** (the name "Flea market \<date\>" is pre-filled).

Result cards also carry hint badges: **✔ n× in your collection**, **⭐ on your
wishlist** and **🛒 on »list name«** when the item is already planned on an
active shopping list – the built-in protection against buying or planning
something twice.

If a figure you found belongs to a **set in your collection** and is still
missing there, instead of "📦 in sets" it says clearly in red: **🧩 missing
from your set: \<set name\>**. At the flea market you see immediately whether a
find closes a gap. If you already own the figure, the normal "in sets" hint
stays.

### 4.4 Adding manually

For everything without a BrickLink number (custom builds, job lots):
**✏️ Add manually** with a free name, your own number, type, quantity,
condition, an optional **"Paid €"** (purchase price) and notes. Such entries
get no automatic market prices – the purchase price you entered and the notes
work normally.

While you type the name the app suggests catalogue matches in parallel; if one
fits, a tap takes over its number and image.

*(Pro)* **"🛒 Onto a list"** puts the entry straight onto a shopping list –
including custom builds that appear in no catalogue.

### 4.5 Custom figures

The switch **"🎨 Custom figure"** in the manual form is meant for your own
builds:

- **The app assigns the number** in sequence (`custom-001`, `-002`, …), which
  you can overwrite if you keep your own scheme.
- **Your own image**: upload one – or, if the scan recognised nothing, use
  **"📷 Use the photo from the scan"** to take the picture you just shot. The
  scan page also has the button **"🎨 Custom figure with this photo"** for
  that.
- Custom figures are **not** looked up at BrickLink; there are no prices or
  catalogue images for them.
- In the collection they live under the theme **"Custom"**.
- In the trading network their picture travels along, downscaled (chapter 12).

---

## 5. The collection

### 5.1 Overview & filters

The **Collection** tab shows all items as cards. At the top: full-text search
(with a 🔍 icon in the field and **✕ to clear**), sort order (newest, name,
value …) and the type filter (all / figures / sets). The key-figure widgets
(quantity, total value) always refer to the current filter.

While the collection loads, a **brick** spins with the note "Loading the
collection …" – the search bar is usable already. So that large collections
open quickly, cards initially build only their header; the detail area appears
when you unfold it.

**The list arrives in blocks.** On opening, the first 60 cards are there; the
rest follow as you scroll – you will not notice unless you jump to the end
with the scrollbar. With 815 entries that is about 2,000 elements on opening
instead of 14,700. Leave the tab and the collection gives its space back,
rebuilding when you return; the data stays in memory meanwhile. If the search
finds nothing, it says so – with a button that clears the filters.

**Sorting by theme.** If you pick "Theme" as the sort order, the collection
shows **collapsible theme cards** – Star Wars, City, Harry Potter, Custom,
"Without a theme" – each with count and value. The app derives the theme for
minifigures from the number prefix (`sw…` → Star Wars) and fetches it for sets
from BrickLink; under *More* it can be filled in for existing data.

> **When BrickLink stays silent:** a set's category id does not always appear
> in BrickLink's category list – then the chain stops at the very first link
> and the set ends up under "Without a theme", even though it is clearly
> listed there. In that case the app asks the **figures inside the set**: if
> there are `sw…` numbers in it, it is Star Wars. Whatever occurs most often
> wins. This requires the set contents to have been loaded already – which
> happens by itself when the set is added.

> The value of a theme card counts figures that sit inside your own sets only
> proportionally – exactly like the total at the top. Otherwise the sum of the
> cards would exceed the total value.

**Your profile remembers the sort order you last chose** – it applies again
next time, on another device too. The default can be set under *More →
Collection sort order*.

The **view switch** next to the filters (icon plus label on wide screens)
toggles between **list view** and **grid** (several figures per row, compact,
with a quantity badge in the corner); the button shows which view you are
switching to, and the choice is remembered per device. In the list the
**product image** also shimmers as a subtle card background. Two cards in a row
are always **the same height**, even when a name wraps.

### 5.2 The card details

Tapping a card opens the details as a **popup** – a centred window above the
list, nearly full screen on a phone. Close it with **✕**, a click beside it or
**Esc**; changes are saved immediately and show up in the list once closed. The
popup shows:

- **Quantity** (± stepper) and **condition** (used/new) – changes take effect
  immediately, without closing the card. **New and used are separate
  entries**: the same figure can sit in the collection once as new and once as
  used, each with its own quantity, its own purchase price and a value matching
  its condition. If you switch an entry's condition to one that already exists,
  the app merges the two (quantities and purchase prices are added up).
- **Purchase price** *(Collector-Pro)* – just type it in; it saves itself when
  you leave the field (or press Enter).
- **Notes** – free text, e.g. origin or peculiarities; they save automatically
  shortly after typing (a "✓ saved" confirms).
- **Prices**: current averages (new/used); the **↻** on the "market prices"
  block fetches them again immediately, and the **price history** shows them as
  a chart (blue = new, green = used) with a link to the BrickLink price page.
- **Tapping the image** opens the large view.
- **Deleting** via the **bin next to the quantity** (it appears as soon as only
  one is left) – with a confirmation.

#### Image missing or wrong?

At the bottom right of the image sits a small **↻ icon**. It fetches the
current catalogue image from BrickLink and stores it permanently – handy for
entries that arrived without an image (for instance through the CSV import).

*(Requires a stored BrickLink key.)*

### 5.3 The same number, recorded twice

The box says **21306**, BrickLink lists the same set as **21306-1**. If you
enter one by hand and scan the other, you have two rows for one set – and the
collection counts it twice.

The app notices and puts a note on the **scan page**:

> 🔔 **The same set recorded twice?**
> "The Beatles Yellow Submarine" is in the collection as 21306 and as
> 21306-1 – on BrickLink that is the same number, the suffix belongs there.
> **Merge them?** [ One copy ] [ Two copies ]

- **One copy** – the same box, recorded twice. One row remains, with the
  quantity of the BrickLink number; the purchase log of the abandoned row
  goes, otherwise the amount would be in there twice.
- **Two copies** – you really own two. The quantities are added up and both
  purchases stay in the log.

The row that stays is the one with the **BrickLink number**: it has prices,
set contents and matches the catalogue – **including its name**. The
catalogue name wins over the one you typed.

**Prevention instead of clean-up.** When you **enter a set by hand**, the app
adds the suffix itself: type `21306` and you get `21306-1` – landing straight
away in the same row as a scanned copy. If the BrickLink keys are configured
the **catalogue name** is taken as well; without keys the typed one stays.
This also applies to the wishlist and the CSV import.

> Only what is unambiguous gets touched: a plain number on a **set**. Figure
> numbers (`sw0312`), part numbers, your own numbers (`manuell-…`) and
> anything that already has a suffix stay as they are.

> **Where the app stays out of it:** for two genuine variants – say `21306-1`
> and `21306-2` – no note appears. Those are two different editions, and only
> you know which one you mean.

### 5.4 Sets and their figures

Brickfolio knows the figure inventories of your sets (via BrickLink, loaded
automatically):

- The set card shows **"👥 3/4"** discreetly in its info line – three of the
  four figures it contains are in the collection; when complete it says
  "👥 4/4 ✔".
- In the set details, **"👥 Figures it contains"** lists every figure with
  ownership badges; missing ones can be put **on the wishlist all at once**
  with one button.
- The other way round, figure cards show **"📦 from your sets"** with a jump to
  the respective set card.
- In the figure details (search as well as collection), sets from **your
  collection** are marked as **yellow chips with ✔** and jump to the set card;
  sets you do not own appear as blue BrickLink links.

### 5.5 Purchase prices & profit *(Collector-Pro)*

Every entry carries a **purchase price** (the total for that line):

- **⚙️ automatic**: without a manual entry the app inserts the BrickLink
  average price of the day it was added (matching the condition). The tooltip
  names the date.
- **✏️ manual**: overwritable at any time via the compact field
  "Paid [amount] €". Manual values are never touched by any automation again.
- When further copies arrive (scan merge, "bought" from the wishlist), the
  purchase price grows by that day's value or the amount you entered.

**Several purchases of the same item.** The same set once at LEGO for 39.99
and once in a shop for 34.99: in the collection that is **one** row with
quantity 2 – number, type and condition are unique. The total was always
right, but which purchase was which could no longer be told.

So below the profit line there is a **purchase log**:

| | | |
| --- | --- | --- |
| 1× | 39.99 € | LEGO Store · 14/06/2026 |
| 1× | 34.99 € | MediaMarkt · 02/07/2026 |

The **＋** at the end of the paid row opens a small window: total price of
this purchase, quantity and optionally the source – all at once. The entry's
quantity grows with it. The
**✕** takes a purchase back, quantity included. The list only appears from the
second entry onwards – with a single one it says nothing that is not already
above. The same applies to figures as to sets.

> The "Paid" field above still holds the **total**, and that is what
> statistics, profit and the shopping lists work with. If you type an amount
> there by hand you mean the whole line – the purchase log is then reset to
> that single entry, so that total and breakdown cannot drift apart.

Below it the **profit line** calculates live: *Value 47.60 € · **+35.10 €***
(green = profit, red = loss; value = current average price × quantity). It
does not repeat the amount paid – that sits one line above in the field.
Without a market price the line stays away.

---

## 6. The wishlist

**Where it lives:** since 1.62.0 wishes, shopping lists and the archive share
the **Lists** tab – three sub-tabs above the view:

| Sub-tab | Contents | Visible |
|---|---|---|
| ⭐ **Wishes** | everything you saved | always |
| 🛒 **Shopping** | active shopping lists, sell list, missing set figures | when there are lists or you are a pro |
| 📦 **Archive** | lists you have worked through | likewise |

Before that these were two entries in the bar for the same question – *what do
I still want, what do I take along?* – and the archive was a button that showed
the same cards with a different symbol. Now it is an area of its own, and
archived lists are dimmed as well.

The **⭐ Wishes** sub-tab collects everything you saved – with image, average
prices and widgets that add up the estimated cost of acquiring it (used/new).

- **✔ Bought!** asks for the condition and moves the item into the collection.
  *Pros* can enter the real purchase price while doing so (empty = BrickLink
  average, automatic ⚙️).
- **Correcting a number:** in the details a wrong number can be replaced
  ("Set") or looked up automatically ("🔍 Auto") – prices are fetched again
  right afterwards.
- Items you already own carry an ownership badge – handy against buying
  something twice.
- If a saved figure belongs to a **set from your collection** and is still
  missing there, the card says **🧩 missing from your set: \<set name\>**.
  Tapping the set jumps straight to it in the collection.

---

## 7. Shopping lists – flea-market mode

The centrepiece for Collector-Pros: shopping in a structured way, with market
knowledge. Standard users see active lists and may book in items that arrived;
everything else is a pro matter.

### 7.1 The typical routine at a stall

**1. Create a list.** Either in the **Lists** tab ("New shopping list …") – or
directly while scanning: the **🛒 List** button always offers **"＋ New list"**
as well, with a pre-filled name such as "Flea market 09/07". Two taps, and the
list exists along with its first item.

**2. Scan through the box.** Put every interesting find on the list via 🛒 –
you pick the **condition** right in the dialog (used is preselected), and if
you already know the price (a tag at the stall) you can optionally enter it in
the **"Spend €"** field – it lands as the purchase price on the list item. Both
can be changed later on the list item itself (the yellow toggle and the spend
field). The same item in the same condition again = the quantity goes up;
**different conditions are separate lines** with their own market values.
Everything calculates per condition.

**3. Read the market value.** The list header continuously shows: *"7 items ·
7 open · market value approx. 86.40 € (per condition)"* – your negotiating
basis, without the seller noticing a thing.

**4. Make an offer: 💰 bundle offer.** The dialog shows the average market
value of all open items and a **red price suggestion** (60 % of the market
value by default – tapping it takes it into the field; the percentage can be
set under More → 💼 Collector-Pro). Once you agree, enter the final price and
press **"Distribute"**:

> **The distribution maths:** the total price is spread across the open items
> in proportion to their market value. Example: a box for 40 €, containing
> figures worth 60 / 30 / 10 € → shares of 24 / 12 / 4 €. Items **without** a
> BrickLink price receive the average share of the others; rounding remainders
> are absorbed by the last item, so the sum matches exactly. The offer can be
> redistributed as often as you like, and individual prices stay correctable
> by hand ("Spend … € ✓").

**5. Book it in at home.** When the finds arrive or get sorted, **anyone**
(even without the pro role) taps **"✔ Got it! Into the collection"**. Confirm
the condition (the stored one is marked with ✓); pros can adjust the price
again – it is pre-filled with the list's purchase price. Items booked in are
**greyed out** with the note *"✔ in the collection, by Finn on 09/07/2026"*.
Into the **notes** of the collection entry the app automatically writes which
list the item came from (e.g. *"From list »Flea market Riem« (09/07/2026)"*) –
an existing note is kept, the hint is appended.

### 7.2 When the item is already in the collection

When booking in an item that already exists, the app asks:

- **＋ In addition** – the quantity goes up; the **average** of the previous
  and the new price is entered as the purchase price.
- **Overwrite** – the collection entry is replaced completely (quantity,
  condition, name, purchase price of the list item).

### 7.3 Purchase-price priority when booking in

1. The price entered in the booking dialog *(pro)* → ✏️ manual
2. The purchase price stored on the list item → ✏️ manual
3. The BrickLink average of the chosen condition → ⚙️ automatic

### 7.4 Archive

Once the **last** item is booked in, the list moves into the **archive**
automatically 🎉 – the third sub-tab in the Lists tab. Only pros can
reactivate lists,
archive them by hand or delete them – and **undo** bookings (↩︎; the
collection entry deliberately stays and is adjusted manually if needed).

---

## 8. The sell list (duplicates)

*(Collector-Pro only – the "📋 Sell list (duplicates)" button under
**Lists → 🛒 Shopping**.)*

At the press of a button Brickfolio produces the list of all items you own
more than once – calculated live, no maintenance needed. The basic rule:

> **"As many figures stay as your sets need – but at least one."**

If a figure exists in both conditions, the keep share is preferably assigned to
the **new** copies – the used ones are the first that can go.

Each line says **why** something stays behind: if the figure is needed for your
own sets, it says "*N× reserved for sets*". If it sits in none of your sets,
only the one keep copy stays – then it simply says "*1 kept*".

Concretely: for every figure the **set demand** is determined (inventory
quantity × how often you own the set). Only what exceeds `max(set demand, 1)`
can go. Examples:

| owned | needed in sets | stays | can go |
|:-:|:-:|:-:|:-:|
| 3× | 2× | 2 | **1×** |
| 2× | 0× | 1 | **1×** |
| 2× | 2× | 2 | *does not appear* |
| 5× | 3× | 3 | **2×** |

Every line shows the condition, "n× owned (m× reserved for sets) → x× can go",
the average unit price for that condition and the sale value; the totals are at
the top. **"As CSV"** exports it for your own calculations, **"Print"**
produces a tidy price list for the stall. Duplicate **sets** themselves can go
normally – the reservation protects the figures *for* the sets, not the sets.

### 8.1 Missing set figures

The counterpart to the sell list sits next to it: **🧩 Missing set figures**
shows, **across all your sets**, which minifigures are still missing.

At the top is the summary ("6 figures missing in 2 of 5 sets · buying them
costs approx. 14.24 €"), below it per figure:

- image, name and number
- **"3× missing (1 of 4 present)"** – the demand takes into account **how
  often you own a set**: two TIE Fighters with two pilots each make a demand of
  4
- **📦 for:** the sets that need it – tappable, jumps to the set
- the average price, if known (from the wishlist or the price history)
- **☆ Save** or the note "⭐ on the wishlist"

At the bottom: **☆ All onto the wishlist**, **As CSV** and **Print** – the
ready-made shopping list for completing your sets.

> **Names and images missing?** These come from the stored set contents, which
> older versions created without them. If a note with the button **🔄 Fetch
> names & images** appears at the top, it gets them from BrickLink (with a
> progress display). With many sets, feel free to press it twice.

---

## 9. The statistics tab

Visible to everyone (📊 in the tab bar), loads automatically when opened:

- **Key figures**: items, distinct items, average value per item, total value
  – *pros* additionally see "total paid" and "profit" (green/red; calculated
  only over entries with a purchase price, so nothing is distorted).
- **Value over time**: the whole collection as a curve, fed from your own price
  log. It calculates with *today's* quantities – the curve answers "what would
  our collection have been worth on day X". It gets more meaningful with every
  week.
- **Breakdown**: bars by type (figures/sets/parts) and condition (new/used),
  each with count, value and percentage.
- **Value by release year**: a bar chart across all years; the top year is
  labelled, tapping shows details.
- **Top 10 by value** with images – and for pros the **biggest value gains**
  (current value minus purchase price, top 5).
- **Spend on lists** *(pro)*: the sum of all purchase prices entered. On the
  overview only **open** lists count deliberately – that is the money currently
  "in transit". A tap opens a popup with **all** lists, archived ones included,
  itemised. There you can tick **"inventoried"** per list: whatever has been
  booked in and taken into the collection drops out of the calculation without
  having to delete the list.

---

## 10. CSV import, export & printing

*(Export & printing under More → 📤 Export & print; the CSV import lives in
the card More → 💼 Collector-Pro.)*

### 10.1 Export & printing (all users)

Collection and wishlist as **CSV** (semicolon-separated, works with
Excel/Numbers) or as a **print view** – a tidy table with page breaks, ideal
for insurance or the display cabinet.

Headings, file names and the number format follow the **language you have
set**, the money columns follow the **currency you have set** – in English the
file is called `brickfolio-collection.csv` and the column `avg used (GBP)`.

### 10.2 CSV import *(Collector-Pro)*

Read whole inventories in one go – an Excel sheet, say, or a BrickLink
inventory list. **"Load sample CSV"** provides a correct template. The format:

```csv
Nummer;Typ;Name;Anzahl;Zustand;Bezahlt;Jahr;Notizen
sw0815;Figur;Shoretrooper;2;Gebraucht;24,50;2016;Flea market Ottobrunn
75154;Set;TIE Striker;1;Neu;89,99;2016;
col424;Figur;;1;Gebraucht;;;empty name: the number is used as the name
```

The rules – deliberately forgiving:

- **Only "number" is required**; column order does not matter, detection is by
  column name (English works too: `qty`, `condition`, `paid` …).
- Separator semicolon **or** comma (detected automatically).
- Defaults: type figure, quantity 1, condition used, empty name → number.
- "Paid" understands German amounts ("24,50", with € too) and is taken over as
  a ✏️ manual purchase price.
- **Existing items** are merged (quantity added, purchase price summed).
- Faulty rows do not abort anything – they are skipped and reported with their
  line number ("3 new, 1 merged, 2 errors").

Names, images, prices, years and set contents are fetched by the app in the
background after the import (see chapter 13) – with large imports that takes a
while.

---

## 11. Backup, restore & updates

### 11.1 Backup (admin)

**More → Backup → 💾 download** produces a JSON file with *everything*: users
(including password hashes), collection, wishlist, shopping lists, price
histories, set links and settings. **📥 restore** brings that state back
completely – after a confirmation showing its date; **all current data is
replaced**. Backups without an admin user are rejected (lock-out protection).

**It also happens automatically:** Brickfolio writes a consistent backup of the
database to `data/backups/` every day and keeps the last 14 daily snapshots
(adjustable via the environment variable `BACKUP_KEEP`, 0 turns it off). The
backup card shows the date of the last automatic backup. The daily snapshots
can be selected in the backup card, **⬇ downloaded** (for your own external
storage, say) and **↩︎ restored directly** – the current state is automatically
written away as an additional backup while doing so, so the action is
reversible.

Still a recommendation: pull an extra JSON backup before bigger operations –
and anyone running a NAS backup (Hyper Backup, for instance) should include the
`data/` folder, so a hardware failure is covered too.

### 11.2 Applying updates

Brickfolio tells you itself: the card **More → 🔄 Version & updates** (admin)
compares the installed version against the latest GitHub release –
automatically at app start and when opening the More tab (cached server-side
for 6 hours), immediately via "Check for updates". If an update is waiting, a
toast and a yellow banner with a link to the release notes appear.

How you apply it depends on how you installed.

**With the ready-made image** (the usual way, see 2.2):

```bash
cd /path/to/brickfolio
docker compose pull && docker compose up -d
```

On a Synology the same works **without a shell**: *Container Manager → Project
→ brickfolio → Action → Build and restart*.

> **`update.sh` is not here.** The script belongs to the source code and sits
> neither in the image nor in your folder if you only fetched the
> `docker-compose.yml`. The two commands above do the same – you only have to
> take the **snapshot** yourself: in the app under *More → Backup*. If you
> want the convenience, fetch the script once:
>
> ```bash
> curl -sLO https://raw.githubusercontent.com/Melle79/brickfolio/main/update.sh
> ```

**Built from source:**

```bash
cd /path/to/brickfolio
sudo bash update.sh
```

The script first takes a **database snapshot** (the last three are kept) and
then works out from your `docker-compose.yml` how the installation runs:

- if it says `image: ghcr.io/…`, it pulls the new image (seconds)
- if it says `build: .`, it fetches the source from GitHub and rebuilds

**In both cases:** your `docker-compose.yml` and the `data/` folder are
untouched – that is where the database, the backups and your uploaded images
live. Database migrations run automatically on start and are idempotent;
updating repeatedly never hurts. Going *back* to an older version is **not**
provided for: migrations only extend. If you want that anyway, restore the
backup first.

#### Updating from inside the app *(optional)*

With a small helper on the server it also works without SSH: the card
**Version & updates** then shows the buttons **Now**, **In 1 minute** and
**In 5 minutes**.

> For this you need **both** scripts on the server – including with an
> installation from the ready-made image, where they do not come along:
>
> ```bash
> cd /path/to/brickfolio
> curl -sLO https://raw.githubusercontent.com/Melle79/brickfolio/main/update.sh
> curl -sLO https://raw.githubusercontent.com/Melle79/brickfolio/main/update-watch.sh
> ```
>
> Without them the buttons **do not appear at all** – the app shows a note
> instead. So no dead button leads nowhere.

How it goes:

1. Every signed-in browser shows a countdown at the top ("Update in 1:00
   minutes – please finish your input"). While it runs, the admin can
   **cancel**.
2. Then a **lock screen** appears everywhere: "Installing the update".
3. As soon as the server is back, **the browsers reload themselves** – even if
   the tab was in the background meanwhile.

**Why a helper?** The app runs in a container and cannot rebuild itself. So it
only writes the marker `data/update-requested.json`; the script
`update-watch.sh` on the server picks it up and starts `update.sh`. That way
the app needs **no Docker access** – handing that into the container would
effectively be root on the server.

**Setting it up** – have `update-watch.sh` called every minute (the update
itself takes one to three minutes anyway). On a Synology: Control Panel → Task
Scheduler → Create → Scheduled Task → User-defined script.

| Tab | Setting |
|---|---|
| General | User: **`root`** (otherwise no `docker compose`) |
| Schedule | Daily · start `00:00` · "Continue running within the same day" ✔ · every minute · Last run time: **`23:59`** |
| Task Settings | `sh /path/to/brickfolio/update-watch.sh` |

> ⚠️ "Last run time" starts at `00:59` – the task would then only run during
> the first hour of the day. Do set it to `23:59`.

On Linux with cron: `* * * * * sh /path/to/brickfolio/update-watch.sh`

**Several instances:** best to use **one task per instance** – that way you see
per instance whether it ran. If you put everything into one task, append
`|| true` to each line, otherwise an error in the first line aborts the second
as well.

**Is the helper running?** The card says so: "✅ The update helper is running" –
or it names the reason if not ("has never reported in" → check the path or the
user; "last ran X hours ago" → check the schedule). Without the helper the
buttons do not appear at all, so the app never waits for an update that will
never come. A log of every run: `data/update-watch.log`.

---

## 12. The trading network

Several Brickfolio instances – in one family or a circle of friends, say – can
connect: everyone publishes the items they want to pass on, sees what the
others offer and writes messages about them. All voluntary; without a
connection the tab simply is not there.

### 12.1 What lives where

The go-between is a small **hub**. Important to understand:

- The hub holds **only the published offers** and the conversation data. Your
  collection, prices, notes and shopping lists **never** leave your own
  instance.
- **Messages are end-to-end encrypted.** The hub cannot read them; it only
  keeps them until the other side collects them, then deletes them. The
  readable history lives on the instances involved – even long after the hub
  has deleted the envelopes.

> **A limitation worth knowing.** Encryption uses the other side's public key
> – and **those keys are distributed by the hub**. Whoever controls the hub
> could hand out one of their own instead of the real one and read along
> without it being noticed. That is not a backdoor in the program, but it is
> the point at which you have to trust the hub.
>
> Since v1.68.0 there are two things against that:
>
> 1. **The instance remembers the key the first time it sees it.** If a
>    different one turns up later, **nothing is sent** – it stops, with a
>    message. Such a change can be harmless (the other side reinstalled);
>    the only way to tell is to ask. Once it is cleared up, an admin confirms
>    the new key.
> 2. **A safety number to compare.** In a conversation, "🔐 Compare the safety
>    numbers" folds open two short rows of digits: yours and the other side's.
>    Read them out over the phone once – if they match on both sides, nobody
>    is in between. They only change when the key really changes.

### 12.2 Joining

To take part you need an **invite code** from somebody who is already in.
Enter it under **More → Trading network**: the code and the display name you
want in the network, then "Join". The wizard at the very first start (2.3)
asks for the same thing.

The display name is unique network-wide and at least four characters long. It
can only be changed by the hub admin.

**Inviting others** is allowed for every connected member: "✉️ Invite a
friend" in the Trade tab. Everyone has a quota of **three** invitations and can
request more from the hub admin. A code works once.

### 12.3 What I offer

The **Trade** tab has three areas. Under **📤 My selection** is what goes into
the network:

- You pick individual items in the **collection**: open a card → "🤝 Offer it
  in the trading network".
- "➕ Take over spares" fetches everything from the sell list (duplicates, see
  chapter 8) in one go.
- For figures you own several times you pick the **quantity** that is offered –
  out of three Yodas, just one if you like.
- Every item says whether it is **already published** or still waiting. What
  sits in the hub but is no longer selected here is reported at the top – it
  disappears the next time you publish.

The selection only becomes visible through **"📤 Publish the selection"**
(admin). Until then nothing changes in the network. Custom figures travel with
a downscaled thumbnail so the other side does not just see a placeholder.

### 12.4 Offers and conversations

Under **🔎 Offers** you find the other members' items, with a search field over
name and number. Tapping a card opens the request window with a suggested
message you can overwrite. If a conversation about that offer is already
running, the chat opens directly instead – the card says so too ("requested ·
open").

Under **💬 My conversations** are all the chats. In an open chat new messages
arrive **on their own**, without "fetch". Your own messages say "on its way …"
or "delivered ✓".

The conversation also has:

- **✔ Accept** / **✖ Decline** – declining closes the window
- **🗑 Delete** – removes the conversation here and in the hub, along with the
  envelopes on the other side
- **⚑ Report** – see below

If the other side takes an item out of the network, the conversation and the
area above the history say **"no longer offered"**.

### 12.5 Reporting

If something goes wrong, "⚑ Report" sends a report to the hub admin. The
tick **"Include the conversation"** is the only way a history ever becomes
readable: your instance decrypts it and discloses it voluntarily. Without the
tick the admin only sees your reason. There is no back door in the hub.

### 12.6 When access has been blocked

A hub admin can block access. The Trade tab then shows a clear notice. What it
means:

- Offers and new messages are no longer possible, and your own offers
  disappear for everyone else.
- **Existing conversations stay readable** – they live locally after all.
- **Nothing is lost.** After being unblocked everything continues without
  reconnecting; messages that arrived while you were blocked are delivered
  afterwards.

Hence the advice on the notice: **do not disconnect.** Disconnecting releases
the account, and the way back gets more awkward.

### 12.7 Administration

Managing members, deciding invitation requests, looking at reports, tidying up
offers – that does **not** happen in the app but in a separate admin console.
That keeps administrative rights out of the family app.

---

## 13. The price automation in detail

So it is clear what happens by itself, and when:

**Fetching prices.** BrickLink average prices (new & used) are fetched:
(1) immediately when an item is added, (2) manually via "update prices" in the
details, (3) automatically by the **background job**: it runs every **12
hours**, takes on items whose prices are older than **7 days** – at most **40
per run** and table, with a 2 s pause per request so as not to burden
BrickLink. The result: no item is ever automatically older than a good week.

**Price history.** Every fetch creates a history point – at most **one per 20
hours** per item. The value curve in the statistics tab is built from exactly
these points. A manual fetch within those 20 hours updates the most recent
point instead of creating a new one (the chart stays clean).

**Price log.** Under **More → 📈 Price log** *(Collector-Pro)* the app lists
the most recent price updates across all items – with date, item, the prices
found and a badge saying whether the point came about **automatically**
(background job) or **manually** (the ↻ button). So it is always traceable when
which prices were recorded.

**Purchase-price automation.** Entries without a manual purchase price receive
the day's average as a ⚙️ value at the first price fetch (see 5.4). Prices set
manually always stay untouched.

**Taking a set's figures with it.** When a **set** moves into the collection –
by photo, search, wishlist, shopping list or manually – the app then asks which
of the minifigures it contains are included. All are preselected, individual
ones can be unticked, and "take none" skips the question. The condition is
pre-filled from the set and can be changed; figures that sit in the set more
than once are recorded more than once. Without a BrickLink key, or for sets
without minifigures, the question does not appear.

**A bin instead of a minus.** If only **one** copy of an item is left, the
quantity button shows a 🗑 instead of the −. Tapping it deletes the entry –
with the same confirmation as the delete button and, for sets, including the
figures question.

**The same when deleting.** When a set is removed from the collection, the app
asks whether its figures should go too. It suggests exactly the number that
belongs to that set: if you own a figure three times and two sat in the set, it
is reduced to **one** rather than deleting everything. "Keep figures" removes
only the set.

**How the total value comes about – and why set figures only count once.** The
value of an entry is *average price × quantity*, matching the recorded
condition. A **set price** at BrickLink, however, is for the *complete* set –
the minifigures are already in it. Anyone recording sets **and** their figures
separately (which makes sense for the overview) would otherwise have them twice
in the total.

So the app calculates like this: **sets count in full**, and of every figure
only those copies count that are **not** sitting in a set of yours. Bound are
*number of sets owned × how often the figure is in the set*, at most as many as
you actually have. If a set contains two stormtroopers, you own the set once
and recorded the figure 3×, then two sit in the set and **one counts** as a
genuine extra. With mixed conditions, matching conditions are assigned first.
How much was deducted is shown openly under the tiles in the statistics.

The deduction only applies where sets and figures meet in **one** number: total
value, the collection's value widget with filter *All*, the breakdown by
type/condition, value by release year and the value curve. If you filter to
**figures** or **sets**, the **full** value of that group appears; individual
cards and the **Top 10** always show the full individual value. The **quantity**
stays unchanged – the figures are physically yours after all – and
**paid/profit** still calculates with the full individual value.

**Other background work:** missing release years are filled in, and set
contents (figure inventories) are loaded for new sets. CSV imports and manual
numbers (`manuell-…`, `fig-…`) without a BrickLink equivalent stay without a
price – everything else looks after itself.

---

### 13.1 Price region and currency

By default BrickLink delivers the **worldwide** average in euros. Under
**More → 🌍 Price region** (admin) you can set both sides:

**Region** – 21 countries (Germany, Austria, Switzerland, United Kingdom,
Ireland, United States, Canada, Australia, New Zealand, Netherlands, Belgium,
France, Italy, Spain, Portugal, Poland, Czechia, Sweden, Denmark, Norway,
Finland), seven regions (Europe, North America, South America, Asia, Oceania,
Africa, Middle East) or worldwide.

**Currency** – euro, British pound, US dollar, Swiss franc, Canadian and
Australian dollar, New Zealand dollar, Swedish, Danish and Norwegian krone,
złoty, Czech koruna. The conversion happens **at BrickLink**: the app sends the
currency code along and stores what comes back. It keeps no exchange rates of
its own – so there is nothing that could go stale.

The two are **independent**: if you live in Germany but buy on the British
market, set the region to United Kingdom and the currency to euro – or the
other way round.

**On first start** the setup wizard (step 2) asks for both and suggests what
matches your browser's language settings: `en-GB` leads to United Kingdom and
pound, `en-US` to United States and dollar, `de-DE` to Germany and euro.
Changing the country pulls the matching currency along – a currency you then
pick by hand stays put.

**Important – the two-step fallback:** especially with rarer figures there are
often **no sales at all** in a single country. If BrickLink finds nothing in
the chosen region, the app widens automatically – **first to the surrounding
region, then worldwide**. The second step follows the country: North America
for the United States, Oceania for Australia, Europe for Europe. The first
market with real sales counts. That way no item is left without a price; the
valuation is simply mixed then. (If a region or worldwide is set directly, the
narrower step is skipped.)

**How to spot a fallback price:** if an average price does not come from the
region you set, a small **flag** sits next to it – 🇪🇺 for Europe, 🌍 for
worldwide. In the detail price card a tooltip explains why. Prices from the
region you set stay without a flag, so at a glance you can tell which ones are
"really German" (or Austrian/Swiss).

**Converting an existing collection.** After a change, all stored prices still
come from the old region – **or from the old currency**. Both count the same:
the card shows how many items are affected and offers **🔄 Recalculate prices
now**. Until then old amounts would sit under a new symbol, and that would
simply be wrong.

> Every item costs **two BrickLink calls** (new and used), and BrickLink has a
> daily quota. So the app works in small portions and shows the progress ("120
> converted, 340 to go …"). With large collections feel free to let it run over
> several days – the state is kept, and it always continues where it left off.

Items BrickLink does not know are skipped and ticked off, so the run does not
get stuck on one number.

**Catching up on items without a price.** If the card says "*X* items still
have no price", those were mostly numbers without sales in the chosen region.
**🔄 Fetch missing prices again** re-values exactly those – with the two-step
fallback Europe → worldwide. That also runs in portions. Whatever still has no
price afterwards really was never sold anywhere; such items honestly stay as
"without a price" rather than repeating the run endlessly.

### 13.2 The price log

**More → 📈 Price log** *(Collector-Pro)* lists the most recent recordings with
time, item, prices and source (`auto` or `manual`). Above it is stated **for
how many items the price fetch is older than seven days** – so you see at a
glance how current the valuation of your collection is. If all prices are
fresh, a confirmation appears there instead.

---

## 14. Troubleshooting

### 14.1 The error report (admin)

If something breaks in the app, nobody has to write down "what it said" any
more. Every browser error is reported to your own server automatically in the
background and collects under **More → 🐞 Error report** – including those from
the children's devices. Per entry you find the error text, the place in the
code, how often it occurred, when it last happened, which app version and which
browser; under "details" the complete information.

**Identical errors are grouped.** An error that occurs on every page load does
not create a hundred entries but one with a counter. The list keeps the last
100 distinct errors.

**What is not reported:** API keys and the GitHub token are removed from every
text (`***`) before it is stored or sent. The report goes exclusively to your
own server – the only thing that leaves it is what you send as an issue
yourself.

**Noticing that something happened.** A *new* error leaves a note on the start
screen – with the message and a button that jumps straight to the card. Only
admins see it; the error report sits in an admin card, so for everyone else the
note would be a dead end. There is always **at most one** open: a single
problem often triggers several different errors. Once dismissed, the next
**new** error reports again – the same one a second time does not.

**🔔 Notification on your device.** If you want to know even when Brickfolio is
closed, switch on web push in the same card – **per device**, with the
browser's permission prompt. After that a new error sends a message to your
phone or desktop.

> **What goes where.** The keys are created on your server the first time you
> switch it on and stay there – the private part never leaves it. Delivery has
> to go through the push service of the respective browser vendor (Apple,
> Google, Mozilla); web push does not work any other way. That is why the
> message only says "An error has been recorded" – no error text, no number,
> nothing from your collection. The content is encrypted on the way there
> anyway, but what is not in it cannot stand out. **The trading hub is not
> involved.**

Requirements: **https** (so the Cloudflare tunnel or your own certificate – over
plain `http` on the home network browsers allow no notifications) and, on the
iPhone, the app **installed to the home screen**. A **Send a test message**
button checks delivery, so it does not first show at the real error. If the app
is reinstalled, the old address points nowhere – the server clears such entries
away by itself on the next send.

**🩺 Memory trace.** When the browser gives up on the page ("There is a problem
with this page"), it normally leaves nothing behind – no console, no log,
nothing. So the app takes a reading every 30 seconds – JS memory, number of
elements, number of images – and stores it **in the browser**, where it
survives such an abort. After the next start the same card shows what
happened in the two hours before, with a curve.

Vertical lines mark the start of a session. Whether a crash is behind it is
decided by the **goodbye note**: on a deliberate end – reloading, clicking
away, closing – the page leaves a note behind; when the browser kills it, it
does not. The summary therefore tells four cases apart:

| Line | Meaning |
| --- | --- |
| "without saying goodbye" | a real crash |
| "reloaded by hand" | somebody reloaded or pulled down |
| "the app reloaded itself" | e.g. after a server restart |
| "the browser discarded the tab" | it does that when memory runs short |

Every reading also carries the **server's start time**; if it jumps, the
container has restarted.

> **What the number says – and what it does not.** What is measured is the
> **JavaScript memory**. Decoded images and the page structure itself are
> **not** in it. If the curve grows, it is the app. If it stays flat while the
> tab dies anyway, the cause is very likely elsewhere – then it is worth
> looking at `edge://crashes` and the browser's task manager (Shift+Esc) to
> see which tab actually grows. That is a result too.

The trace stays on the device. "📋 Copy the trace" puts it on the clipboard as
text to paste elsewhere.

**An issue at the press of a button.** With a GitHub token stored, "🐙 Create an
issue" turns an entry directly into an issue in the project. The button then
becomes "View issue ↗"; a second click creates no duplicate. Without a token
the error report stays usable – "📋 Copy report" puts the whole list into the
clipboard as text, which you can paste anywhere by hand. "Clear list" tidies
up.

**Creating the token** (once, under "GitHub token" in the same card): on
GitHub under *Settings → Developer settings → Personal access tokens →
Fine-grained tokens* create a token, choose **only this one repository** as the
repository access and set **Issues: Read and write** as the only permission.
The app needs no more – and the token should be able to do no more. It then
lives in your database and is never shown in the interface again.

### 14.2 When BrickLink changes or deletes a number

The BrickLink catalogue is not set in stone: numbers get renamed, duplicate
entries merged, rarely also deleted. If that hits an item in your collection,
its price would silently freeze at the old state. The app speaks up so that
does not happen.

**How it notices.** The app fetches prices for every item every seven days
anyway. If BrickLink suddenly answers "unknown" for a number that used to work,
something happened. A number mistyped by hand, on the other hand, triggers no
notice – it never worked.

**The notice** appears at the top of the **Scan** tab, so on the start screen,
and **stays there until somebody dismisses it with the ✕**. It does not
disappear by itself and does not come back after being dismissed – whoever saw
the matter and decided should not be asked again at every price run.

**The new number.** Only when something really is missing does the app look
into the public [BrickLink Catalog Change
Log](https://www.bricklink.com/catalogLogs.asp) and search there, starting from
the last successful price fetch, for the number change or the merge. In normal
operation that page is not touched at all. If it finds something, the notice
names the new number and **"Use this number"** enters it everywhere:
collection, wishlist, shopping lists, the set-figure links and the price
history. Afterwards the app fetches prices under the new number.

**If the log finds nothing** – because the entry really was deleted, say – the
notice stays anyway, just without a new number. Nothing is lost: the item stays
in the collection with its last known price. You can then correct the number by
hand via "Set BrickLink no." in the card details.

### 14.3 Common stumbling blocks

**An update does not take effect / old interface.** Did the update run
through completely? Which version is running is shown in More → 🔄 Version &
updates; after that a normal reload is enough. With the ready-made image, check
that `docker compose pull` really fetched a new image.

**Prices missing on individual items.** Manual numbers have no BrickLink
equivalent. Freshly imported items are served in portions of 40 – be patient or
press the **↻** on the "market prices" block in the detail popup. No prices at
all? → More → API keys → "Test connection".

**"Collector-Pros only" (403).** The feature needs the pro role – the admin
grants it under More → Manage users.

**The Lists tab is missing.** For standard users it only appears when an active
list exists; after archiving the last list it disappears again. Pros always see
it.

**Login no longer works / user forgotten.** You change your own password via
the profile popup (tap your name at the top right); forgotten passwords are
reset by the admin in user management. If the admin themselves is locked out:
restore the last backup or copy `data/brickfolio.db` back from a backup.

**The camera does not open.** Close the PWA once and reopen it; check the
browser's camera permission. On iOS camera access only works through Safari or
the app installed from the home screen.

**Recognition returns nonsense.** Better light, a neutral background, get
closer – or simply use the text search with the number from the leg print or
the building instructions.

---

## 15. FAQ

**Does Brickfolio need the internet?** For scanning, prices and search: yes
(those APIs live on the net). Your own data still stays entirely on your
server. What works without internet is listed in the README.

**Do BrickLink/Rebrickable cost anything?** No, both API accesses are free –
BrickLink only requires a seller account with a store.

**Can my child break something?** Without the pro or admin role they see
neither purchase prices nor list management, archive or import – they can
collect, wish and book in items that arrived. And there is the backup. 🙂

**Where do the prices come from – and how accurate are they?** They are
BrickLink average prices of the most recent sales (new/used separately). They
are a good orientation, not an appraisal – rare conditions, completeness and
region can differ in reality.

**Why does the value curve start so low?** Recording begins with the setup; at
first only a few items are "priced". Once everything has prices, the curve
shows real market movement.

**Several collections/families?** One Brickfolio instance = one shared
collection. For separate collections simply start a second container with its
own `data/` folder and port.

**Is this legal with the LEGO name?** Brickfolio is a private hobby project.
LEGO® is a trademark of the LEGO Group, which does not sponsor, authorise or
endorse this project; BrickLink and Rebrickable are trademarks of their
respective owners, and their APIs are subject to their respective terms of use.

---

## 16. Appendix

### 16.1 Symbols at a glance

| Symbol | Meaning |
|---|---|
| ⚙️ | purchase price automatic (BrickLink average; date in the tooltip) |
| ✏️ | purchase price entered manually |
| 👥 3/4 (✔) | 3 of 4 set figures present (✔ = complete) |
| 📦 | "sits in your sets" or archive |
| ⭐ / ☆ | on the wishlist / save it |
| 🛒 on »…« | the item is planned on an active shopping list |
| yellow set link with ✔ | this set is in your collection |
| ✔ (greyed out) | list item has been booked into the collection |
| 🛒 | put onto a shopping list |
| 🐞 | error report (admin only, under "More") |

### 16.2 Environment variables

| Variable | Meaning |
|---|---|
| `ADMIN_USER` / `ADMIN_PASSWORD` | Optional: create the admin automatically (otherwise setup in the browser) |
| `BACKUP_KEEP` | How many automatic daily backups to keep (default 14, 0 = off) |
| `DB_PATH` | Path to the SQLite file (default: `/data/brickfolio.db`) |
| `BL_CONSUMER_KEY` / `BL_CONSUMER_SECRET` / `BL_TOKEN` / `BL_TOKEN_SECRET` | BrickLink store API (fallback to the app settings) |
| `REBRICKABLE_KEY` | Rebrickable API (fallback to the app settings) |
| `GITHUB_REPO` | Target repository for issues from the error report (default: `Melle79/brickfolio`) |

### 16.3 CSV import: recognised column names

| Field | recognised names |
|---|---|
| Number *(required)* | Nummer, item_id, no, number |
| Type | Typ, type (values: Figur/minifig/fig, Set, Teil/part) |
| Name | Name |
| Quantity | Anzahl, Menge, qty, quantity |
| Condition | Zustand, condition (Neu/new, Gebraucht/used) |
| Paid | Bezahlt, Kaufpreis, Einkauf, paid |
| Year | Jahr, year |
| Notes | Notizen, notes, Bemerkung |

---

*Happy collecting! Questions, bugs or ideas are welcome as an issue at
[github.com/Melle79/brickfolio](https://github.com/Melle79/brickfolio).* 🧱
