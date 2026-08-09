# Hub-Konsole – Absturz-Reiter

Die Konsole selbst liegt **nicht** in diesem Repo, sondern auf der NAS unter
`/volume1/homes/Sven/brickfolio-hub-admin/`. Hier stehen nur die beiden
Dateien, die für den Reiter „🐞 Abstürze" geändert wurden – damit die
Änderung nachvollziehbar bleibt und bei einem Neuaufsetzen nicht verloren
geht.

**Wichtig:** Die Dateien werden ins Image gebacken, nicht aus dem Ordner
ausgeliefert. Nach einer Änderung ist ein Neubau nötig:

    cd /volume1/homes/Sven/brickfolio-hub-admin
    sudo docker compose up -d --build

Ohne den Neubau ändert sich in der Konsole nichts, und man sucht den Fehler
an der falschen Stelle.
