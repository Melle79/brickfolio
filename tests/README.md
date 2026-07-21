# Tests

Fokus liegt auf der **Wertberechnung** – dem Bereich mit den meisten
zurückliegenden Fixes (Doppelzählung von Set-Figuren, Zustands-Fallback beim
Ø-Preis).

Abgedeckt:

- `test_unit_price.py` – `_unit_price`: Ø-Stückpreis je Zustand inkl. Fallback
- `test_set_bound_map.py` – `_set_bound_map`: wie viele Figuren-Exemplare in
  eigenen Sets stecken (Grundlage der Doppelzählungs-Vermeidung)
- `test_offer_shares.py` – `_distribute_offer_shares`: Gesamtangebot anteilig
  nach Marktwert verteilen (Rundungsrest, Ø-Fallback)
- `test_receive_integration.py` – Integrationstest über den echten Endpoint:
  Einkaufslisten-Artikel »erhalten« (neu/add/replace/manueller Kaufpreis) und
  per »undo« zurücknehmen

## Ausführen

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements-dev.txt
.venv/bin/python -m pytest
```

Die Tests setzen in `conftest.py` `SECRET_KEY`, `DB_PATH` und `FRONTEND_DIR`,
bevor das Backend importiert wird – es wird also **kein** echtes Datenverzeichnis
angelegt und keine laufende Instanz benötigt.
