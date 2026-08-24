FROM python:3.12-slim

WORKDIR /app

# Pillow braucht zur Laufzeit nur die Bibliotheken, nicht den Compiler –
# die Räder sind vorgebaut. Deshalb kein build-essential: Das Abbild wäre
# dreimal so groß, für nichts.
RUN pip install --no-cache-dir \
      "fastapi==0.115.*" "uvicorn[standard]==0.32.*" \
      "requests==2.32.*" "requests-oauthlib==2.0.*" "pillow==11.*"

COPY katalog.py bild.py laeufe.py dienst.py ./

# Der Abzug liegt hier – als Docker-Volume, damit er einen Neubau überlebt.
# Tage an BrickLink-Abrufen und ein Tag Grafikeinheit stecken darin.
VOLUME ["/data"]
ENV DB_PATH=/data/katalog.db

EXPOSE 8320

# Ein Arbeitsprozess, mit Absicht. Die beiden Läufe halten ihren Zustand im
# Speicher (`_katalog_lauf`, `_farb_lauf`); mit mehreren Prozessen sähe jeder
# einen anderen Stand, und „läuft bereits" verhinderte nichts mehr.
CMD ["uvicorn", "dienst:app", "--host", "0.0.0.0", "--port", "8320", \
     "--workers", "1"]
