"""Einmalig: Listennamen nachträglich in die Notizen bereits verbuchter
Artikel schreiben – auch für archivierte Listen. Idempotent (mehrfaches
Ausführen fügt nichts doppelt hinzu)."""
import datetime
import core

with core.db() as conn:
    rows = conn.execute(
        "SELECT si.item_id, si.item_type, si.done_at, sl.name AS list_name "
        "FROM shopping_items si "
        "JOIN shopping_lists sl ON sl.id = si.list_id "
        "WHERE si.done = 1 AND sl.name IS NOT NULL").fetchall()
    updated = 0
    for r in rows:
        d = (datetime.datetime.fromtimestamp(r["done_at"]).strftime("%d.%m.%Y")
             if r["done_at"] else "")
        marker = f"Von Liste »{r['list_name']}«"
        note_add = marker + (f" ({d})" if d else "")
        for c in conn.execute(
                "SELECT id, notes FROM collection "
                "WHERE item_id = ? AND item_type = ?",
                (r["item_id"], r["item_type"])).fetchall():
            notes = c["notes"] or ""
            if marker in notes:
                continue
            new = (notes + ("\n" if notes else "") + note_add).strip()[:1000]
            conn.execute("UPDATE collection SET notes = ? WHERE id = ?",
                         (new, c["id"]))
            updated += 1
    print(f"{updated} Sammlungs-Eintrag/-Einträge um Listennotiz ergänzt")
