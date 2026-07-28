# Brickfolio auf einer Synology-NAS

Zwei Wege. Der erste braucht keine Konsole und ist der empfohlene.

---

## Weg 1: Container Manager (ohne SSH)

Voraussetzung: **Container Manager** aus dem Paket-Zentrum (DSM 7.2 oder
neuer). Bei älterem DSM heißt das Paket **Docker**; dann geht Weg 2.

### 1. Ordner anlegen

In der **File Station** unter `docker` einen Ordner `brickfolio` anlegen, darin
einen Ordner `data`. Ergebnis: `/volume1/docker/brickfolio/data`.

Der Ordner `data` ist der einzige, auf den es ankommt – dort liegt eure
Datenbank. Alles andere ist ersetzbar.

### 2. Projekt anlegen

**Container Manager → Projekt → Erstellen**

| Feld | Eingabe |
|---|---|
| Projektname | `brickfolio` |
| Pfad | `/docker/brickfolio` |
| Quelle | **YAML-Code erstellen** |

In das Textfeld kommt:

```yaml
services:
  brickfolio:
    image: ghcr.io/melle79/brickfolio:latest
    container_name: brickfolio
    restart: unless-stopped
    ports:
      - "8300:8300"
    volumes:
      - ./data:/data
```

**Weiter → Weiter → Fertig.** Der Container Manager lädt das Image und startet
es. Beim ersten Mal dauert das ein bis zwei Minuten (rund 75 MB).

### 3. Aufrufen

`http://<NAS-IP>:8300` – der Einrichtungsassistent übernimmt ab hier.

> Ist Port 8300 belegt, in der YAML die **linke** Zahl ändern, z. B.
> `"8399:8300"`, und die App dann unter `:8399` aufrufen.

### 4. Aktualisieren

**Container Manager → Projekt → brickfolio → Aktion → Erstellen neu starten.**
Damit zieht DSM das aktuelle Image und startet neu; die Datenbank in `data`
bleibt unangetastet.

Wer vorher einen Sicherungspunkt will: in der App unter **Mehr → Sicherung**
die JSON-Datei herunterladen.

---

## Weg 2: Über SSH

Für älteres DSM oder wenn die Konsole ohnehin offen ist:

```bash
sudo mkdir -p /volume1/docker/brickfolio && cd /volume1/docker/brickfolio
sudo curl -sLo docker-compose.yml https://raw.githubusercontent.com/Melle79/brickfolio/main/docker-compose.example.yml
sudo docker compose up -d
```

Aktualisieren später:

```bash
sudo bash update.sh
```

(`update.sh` liegt im Projektordner, wenn ihr den Quellcode geholt habt –
sonst genügt `sudo docker compose pull && sudo docker compose up -d`.)

---

## Von unterwegs erreichbar machen

Ohne Portfreigabe im Router: In der App unter **Mehr → Externer Zugriff**
steckt ein Assistent, der aus einem Cloudflare-Tunnel-Token den fertigen
`docker-compose`-Block baut. Der Token bleibt dabei im Browser – die App
speichert ihn nicht und schickt ihn nirgendwohin.

---

## Häufige Stolpersteine

**„Image kann nicht gefunden werden"** – im Container Manager unter
*Registrierung* ist standardmäßig nur Docker Hub eingetragen. Das stört hier
nicht: Ein Projekt mit vollem Namen (`ghcr.io/…`) zieht direkt, die Suche
braucht man dafür nicht.

**Rechte auf `data`** – wenn der Container nicht startet und im Protokoll von
fehlenden Schreibrechten die Rede ist, gehört dem Ordner `data` der falsche
Besitzer. In der File Station unter *Eigenschaften → Berechtigung* für
`brickfolio` (inkl. Unterordner) Schreibrechte setzen.

**ARM-NAS** (z. B. DS220j, DS223) – funktioniert, das Image gibt es für
`arm64`. Sehr alte 32-Bit-Modelle (`armv7`) werden nicht unterstützt.
