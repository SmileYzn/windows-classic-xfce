#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Gera o index.theme (lista Directories e uma seção por pasta) do tema windows-classic-icons
e cria as pastas <N>x<N>/<contexto> que faltarem (com um .gitkeep, para o Git guardar as vazias).

Os tamanhos do tema ficam na lista TAMANHOS abaixo. Para incluir um tamanho novo:
  1. acrescente-o em TAMANHOS aqui, em TAMANHOS no Icons/src/mapa.py e em
     Icons/build/xp-icons/sizes.txt (rode o resize.sh para gerar a pasta da galeria XP);
  2. rode:  python3 Icons/src/gerar-index.py
  3. depois:  python3 Icons/src/aplicar-lista.py   e   python3 Icons/src/mapa.py

O cabeçalho do index.theme (tudo antes de "Directories=") é preservado.
"""

import os

AQUI = os.path.dirname(os.path.abspath(__file__))
TEMA = os.path.join(os.path.dirname(AQUI), "windows-classic-icons")
INDEX = os.path.join(TEMA, "index.theme")

TAMANHOS = [16, 22, 24, 32, 36, 48, 64, 96, 128]
CONTEXTOS = {                   # pasta -> Context= do index.theme
    "actions": "Actions", "animations": "Animations", "apps": "Applications",
    "categories": "Categories", "devices": "Devices", "emblems": "Emblems",
    "mimetypes": "MimeTypes", "places": "Places", "status": "Status",
}


def main():
    with open(INDEX, encoding="utf-8") as f:
        texto = f.read()
    cab = texto[:texto.index("Directories=")]
    pastas = ["%dx%d/%s" % (t, t, c) for t in TAMANHOS for c in sorted(CONTEXTOS)]
    saida = cab + "Directories=" + ",".join(pastas) + "\n"
    for t in TAMANHOS:
        for c in sorted(CONTEXTOS):
            saida += "\n[%dx%d/%s]\nContext=%s\nSize=%d\nType=Fixed\n" % (t, t, c, CONTEXTOS[c], t)
    novas = 0
    for p in pastas:
        d = os.path.join(TEMA, p)
        if not os.path.isdir(d):
            os.makedirs(d)
            open(os.path.join(d, ".gitkeep"), "w").close()
            novas += 1
    with open(INDEX, "w", encoding="utf-8") as f:
        f.write(saida)
    print("OK: %d tamanhos x %d contextos = %d pastas (%d criadas) em %s"
          % (len(TAMANHOS), len(CONTEXTOS), len(pastas), novas, INDEX))


if __name__ == "__main__":
    main()
