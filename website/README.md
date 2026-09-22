# Die Projektseite – wo sie jetzt liegt

[brickfolio.cc](https://brickfolio.cc) hat seit dem 22.09.2026 ein
**eigenes, nicht öffentliches Repo**: `Melle79/brickfolio-website`. Die
Quellen sind mit ihrer Geschichte dorthin umgezogen.

Warum getrennt: Hier gehört das **Programm** hin. Die Werbeseite teilt
damit keinen Code, wird von Hand veröffentlicht (`npx wrangler deploy`,
kein Workflow) und trägt Bildschirmfotos aus der eigenen Sammlung – die
müssen vor jeder Veröffentlichung auf Namen durchgesehen werden. Das ist
ein anderer Rhythmus als der des Repos hier.

**Änderungen gehören ins Seiten-Repo**, nicht hierher:

    gh repo clone Melle79/brickfolio-website
    # ändern, commiten, pushen – dann veröffentlichen:
    npx wrangler deploy

Die Seite selbst bleibt öffentlich erreichbar; nur ihre Quellen sind es
nicht mehr.
