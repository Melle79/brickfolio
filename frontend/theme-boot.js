/* Design vor dem ersten Zeichnen setzen, damit nichts aufblitzt.

   Steht bewusst in einer eigenen Datei und nicht als `<script>` im Dokument:
   Die Sicherheits-Regeln der App erlauben nur Skript aus der App selbst
   (`script-src 'self'`). Inline blockierte der Browser es – still, und wer
   ein dunkles Design nutzte, sah bei jedem Laden kurz das helle aufblitzen.

   Muss synchron im `<head>` laufen, vor dem Stylesheet-Aufbau. Deshalb hier
   nur diese paar Zeilen und nichts sonst. */
(function () {
  try {
    var t = localStorage.getItem("bf_theme");
    var c = { galaxy: "#0C1322", nova: "#0A0E1A" }[t];
    if (t && t !== "classic") {
      document.documentElement.dataset.theme = t;
      var m = document.querySelector('meta[name="theme-color"]');
      if (m && c) m.content = c;
    }
  } catch (e) { /* privater Modus o. Ä. */ }
})();
