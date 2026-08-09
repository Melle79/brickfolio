# Hub-Konsole – wo sie wirklich liegt

Die Konsole hat ein **eigenes Repo**: `Melle79/brickfolio-hub-admin`.
Betrieben wird sie auf der NAS unter
`/volume1/homes/Sven/brickfolio-hub-admin/`, wo `update.sh` den Stand von
dort holt und den Container neu baut.

Hier lagen bis zum 09.08.2026 Kopien von `app.js` und `index.html` – als
Sicherheitsnetz angelegt, weil das eigene Repo damals nicht bekannt war.
Sie sind wieder entfernt: Eine zweite Quelle für dieselbe Datei ist kein
Netz, sondern eine Falle. Genau daran ist es schon einmal fast schiefgegangen
– das Konsolen-Repo stand still, während auf der NAS von Hand weitergebaut
wurde, und der nächste Lauf von `update.sh` hätte alles zurückgedreht.

**Änderungen gehören ins Konsolen-Repo**, nicht hierher:

    gh repo clone Melle79/brickfolio-hub-admin
    # ändern, commiten, pushen – dann auf der NAS:
    cd /volume1/homes/Sven/brickfolio-hub-admin && sudo sh update.sh

Zwei Dateien liegen bewusst **nur** auf der NAS und in keinem Repo:
`htpasswd` (Passwort vor der Konsole) und `public/token.js` (hinterlegter
Admin-Token). `update.sh` entpackt das Archiv mit `tar xz` über den Ordner –
läge dort ein Platzhalter, überschriebe er die echte Passwortdatei.
