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

  /* **Notausgang für den Startbildschirm.** Er ist von Haus aus sichtbar
     und deckt die ganze Seite ab; weggenommen wird er von `app.js`, wenn
     die erste Ansicht steht. Bricht die Datei ab – Syntaxfehler nach einem
     halben Update, blockiert von einer Erweiterung –, läge der Schirm für
     immer über einer App, die man nicht mehr bedienen kann.

     Lieber ohne Startbild als ausgesperrt. Sechs Sekunden sind dabei weit
     jenseits jedes normalen Starts; wer hier ankommt, hat ohnehin ein
     Problem, das ein Startbild nicht schöner macht.

     Gehört hierher und nicht als `<script>` ins Dokument: `script-src
     'self'` blockiert Inline-Skript still – die Sicherheitsprobe
     `test_kein_inline_skript` hat genau das beim Einbau gemeldet. */
  setTimeout(function () {
    var s = document.getElementById("splash");
    if (s) s.remove();
    // Die Marke hält den Inhalt unsichtbar – sie muss hier mit weg,
    // sonst stünde die App zwar da, aber durchsichtig.
    if (document.body) document.body.classList.remove("splash-laeuft");
  }, 6000);
})();
