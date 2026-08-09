#!/bin/zsh
# Aufpasser für die Dauerläufer auf dem Mac mini – alle 5 Minuten.
#
# Zwei Dinge sollen stehen, und für beide gab es bisher niemanden, der
# nachsieht:
#
#   1. Die Home-Assistant-VM. `ha-vm-autostart.sh` läuft mit `RunAtLoad`,
#      also **einmal bei der Anmeldung**. Stirbt die VM mittags, holt sie
#      niemand zurück – und der stündliche HA-Wächter kann es nicht melden,
#      weil er selbst über HA meldet. Genau der Fall, in dem man nichts
#      erfährt.
#   2. Die Fernsteuer-Sitzung für die Claude-App. Sie läuft in einem
#      `screen` und überlebt keinen Neustart des Rechners.
#
# Unterschied in der Behandlung, und der ist wichtig:
#
#   HA wird **repariert** – der Autostart kann das.
#   Die Sitzung wird nur **gemeldet**. `claude remote-control` braucht ein
#   echtes interaktives Terminal, um seine Verbindung aufzubauen; losgelöst
#   gestartet läuft der Prozess zwar, verbindet sich aber nie (geprüft am
#   09.08.2026: sechs Zeilen Protokoll, keine Registrierung). Ein Neustart
#   von hier aus würde also eine Sitzung vortäuschen, die es nicht gibt.
#
# `utmctl` funktioniert **nicht** über SSH ("does not work from SSH
# sessions"). Deshalb ist das hier ein LaunchAgent und kein Skript, das man
# von außen anstößt.

HA="http://192.168.0.222:8123"
AUTOSTART="$HOME/bin/ha-vm-autostart.sh"
LOG="$HOME/Library/Logs/aufpasser.log"
ZUSTAND="$HOME/.aufpasser-zustand"
RC_NAME="bfrc"
TOKEN_DATEI="$HOME/.ha_token"

# Erst nach drei Fehlschlägen in Folge eingreifen (~15 Minuten). Ein
# einzelner Aussetzer ist oft ein Neustart der VM, der gerade läuft – da
# hineinzugrätschen macht es schlimmer.
GRENZE=3
# Danach eine halbe Stunde Ruhe, damit sich nichts aufschaukelt.
RUHE=1800

exec >> "$LOG" 2>&1

melde() {
  [[ -r "$TOKEN_DATEI" ]] || return 0
  local titel="$1" text="$2"
  curl -s -m 20 -X POST \
    -H "Authorization: Bearer $(cat "$TOKEN_DATEI")" \
    -H "Content-Type: application/json" \
    -d "{\"title\":\"$titel\",\"message\":\"$text\"}" \
    "$HA/api/services/notify/mobile_app_svens_iphone" > /dev/null
}

jetzt=$(date +%s)
fehlschlaege=0
letzte_reparatur=0
[[ -r "$ZUSTAND" ]] && read fehlschlaege letzte_reparatur < "$ZUSTAND"

# ---------------------------------------------------------------- 1) HA
code=$(curl -s -m 8 -o /dev/null -w "%{http_code}" "$HA/" 2>/dev/null)
if [[ "$code" == "200" || "$code" == "301" || "$code" == "302" ]]; then
  if (( fehlschlaege >= GRENZE )); then
    echo "$(date '+%F %T') HA ist wieder da (nach $fehlschlaege Fehlschlägen)."
    melde "🏠 Home Assistant ist wieder da" "Nach $((fehlschlaege * 5)) Minuten Ausfall."
  fi
  fehlschlaege=0
else
  fehlschlaege=$((fehlschlaege + 1))
  echo "$(date '+%F %T') HA nicht erreichbar (HTTP ${code:-–}), Fehlschlag $fehlschlaege."
  if (( fehlschlaege >= GRENZE )) && (( jetzt - letzte_reparatur > RUHE )); then
    if [[ -x "$AUTOSTART" ]]; then
      echo "$(date '+%F %T') Starte die VM über $AUTOSTART."
      "$AUTOSTART"
      letzte_reparatur=$jetzt
    else
      echo "$(date '+%F %T') $AUTOSTART fehlt oder ist nicht ausführbar."
    fi
  fi
fi

# ------------------------------------------------- 2) Fernsteuer-Sitzung
if ! /usr/bin/screen -ls 2>/dev/null | grep -q "$RC_NAME"; then
  # Nur einmal je Ruhezeit melden – sonst kommt alle fünf Minuten dieselbe
  # Nachricht, und die wischt man irgendwann weg.
  marke="$HOME/.aufpasser-rc-gemeldet"
  letzte=0
  [[ -r "$marke" ]] && letzte=$(cat "$marke")
  if (( jetzt - letzte > RUHE )); then
    echo "$(date '+%F %T') Fernsteuer-Sitzung '$RC_NAME' läuft nicht."
    melde "📱 Claude-Sitzung ist weg" \
      "Die Fernsteuerung auf dem Mac mini läuft nicht mehr. Sie braucht ein echtes Terminal: ssh macmini, dann TERM=xterm-256color screen -S bfrc, darin cd ~/brickfolio && claude remote-control --name 'Brickfolio – unterwegs' --permission-mode acceptEdits, dann Strg-A D."
    echo "$jetzt" > "$marke"
  fi
else
  rm -f "$HOME/.aufpasser-rc-gemeldet"
fi

echo "$fehlschlaege $letzte_reparatur" > "$ZUSTAND"
