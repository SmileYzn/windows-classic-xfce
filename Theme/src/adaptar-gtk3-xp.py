#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Ajustes e imagens geradas do tema GTK 3 (Theme/windows-classic/gtk-3.0) para o
esquema "Windows Clássico" do Windows XP.

1. Sombra escura das bordas 3D. No arquivo de tema oficial do XP
   (I386/CLASSIC.TH_):

       ButtonDkShadow=64 64 64   ->  #404040

   O preto dos desenhos (setas, marcas, "X") e o contorno do botão padrão
   (WindowFrame=0 0 0) continuam pretos. Por isso o script garante que:
     - @border_dark é #404040 no gtk.css;
     - os retângulos de foco pontilhados continuam pretos (@outline_color);
     - nas imagens, só o preto das linhas de borda vira #404040.

2. Caixinhas +/- das árvores (assets/treeview-*.png), desenhadas como no
   Explorer do XP, e o gtk.gresource que as entrega ao GTK (veja
   gerar_gresource()).

O script é idempotente: rodar de novo não muda nada.
Uso:  python3 Theme/src/adaptar-gtk3-xp.py
Dependências: ImageMagick e glib-compile-resources
    sudo pacman -S --needed imagemagick glib2
"""

import math
import os
import re
import subprocess
import tempfile

AQUI = os.path.dirname(os.path.abspath(__file__))
GTK3 = os.path.join(os.path.dirname(AQUI), "windows-classic", "gtk-3.0")

PRETO = (0, 0, 0)
DKSHADOW = (0x40, 0x40, 0x40)

# Imagens sem bordas 3D (só desenho ou arte): ficam como estão
IGNORAR = re.compile(  # treeview-* é desenhado por desenhar_expansores()
    
    r"(^arrow-|combobox-arrow-down|^icon-|hglass_|^Wait|throbber|"
    r"status_badge|thumbnail|expander_|treeview-)")

# Botão padrão: o contorno externo preto é o WindowFrame e continua preto
SO_SEGUNDA_LINHA = {"dialog_button_focus.png", "dialog_button_active.png",
                    "button_pressed.png"}


def ler(caminho):
    w, h = map(int, subprocess.run(
        ["magick", "identify", "-format", "%w %h", caminho + "[0]"],
        check=True, capture_output=True, text=True).stdout.split())
    dados = subprocess.run(["magick", caminho + "[0]", "-depth", "8", "rgba:-"],
                           check=True, capture_output=True).stdout
    return w, h, bytearray(dados)


def gravar(caminho, w, h, dados):
    subprocess.run(["magick", "-size", "%dx%d" % (w, h), "-depth", "8",
                    "rgba:-", "PNG32:" + caminho], input=bytes(dados), check=True)


def recolorir(caminho):
    nome = os.path.basename(caminho)
    if IGNORAR.search(nome):
        return 0
    w, h, d = ler(caminho)

    def px(x, y):
        i = (y * w + x) * 4
        return tuple(d[i:i + 3]), d[i + 3]

    opacos = [(x, y) for y in range(h) for x in range(w) if px(x, y)[1] > 0]
    if not opacos:
        return 0
    x0 = min(x for x, _ in opacos); x1 = max(x for x, _ in opacos)
    y0 = min(y for _, y in opacos); y1 = max(y for _, y in opacos)
    radio = nome.startswith("radio-")
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2

    n = 0
    for x, y in opacos:
        cor, a = px(x, y)
        if cor != PRETO or a < 255:
            continue
        if radio:
            borda = math.hypot(x - cx, y - cy) > 3       # arco, não o ponto
        else:
            anel = min(x - x0, x1 - x, y - y0, y1 - y)   # distância à borda
            borda = anel == 1 if nome in SO_SEGUNDA_LINHA else anel <= 1
        if borda:
            i = (y * w + x) * 4
            d[i:i + 3] = bytes(DKSHADOW)
            n += 1
    if n:
        gravar(caminho, w, h, d)
    return n


def ajustar_css():
    p = os.path.join(GTK3, "gtk.css")
    with open(p) as f:
        s = f.read()
    s = s.replace("@define-color border_dark #000000; /* Windows Theme: buttondkshadow */",
                  "@define-color border_dark #404040; /* Windows Theme: buttondkshadow (XP clássico: 64 64 64) */")
    with open(p, "w") as f:
        f.write(s)
    # retângulos de foco (DrawFocusRect) continuam pretos
    for nome in ("gtk-widgets.css", "gtk-checks_radio.css"):
        p = os.path.join(GTK3, nome)
        with open(p) as f:
            s = f.read()
        s = s.replace("1px dotted @border_dark", "1px dotted @outline_color")
        with open(p, "w") as f:
            f.write(s)


def desenhar_expansores():
    """Caixinhas +/- das árvores como no Explorer clássico do XP: 9x9 px,
    borda ButtonShadow (#808080), fundo branco e sinal preto de 5 px.
    A caixa fica fora do realce da seleção no Windows, então as variantes
    '-inverted' (linha selecionada) são iguais às normais."""
    cinza, branco, preto = (128, 128, 128, 255), (255, 255, 255, 255), (0, 0, 0, 255)
    x0, y0, lado = 4, 3, 9
    for aberto in (False, True):
        d = bytearray(16 * 16 * 4)
        for y in range(16):
            for x in range(16):
                if not (x0 <= x < x0 + lado and y0 <= y < y0 + lado):
                    continue
                cx, cy = x - x0, y - y0
                if cx in (0, lado - 1) or cy in (0, lado - 1):
                    cor = cinza
                elif (cy == 4 and 2 <= cx <= 6) or (not aberto and cx == 4 and 2 <= cy <= 6):
                    cor = preto
                else:
                    cor = branco
                i = (y * 16 + x) * 4
                d[i:i + 4] = bytes(cor)
        base = "treeview-opened" if aberto else "treeview-closed"
        for sufixo in ("", "-inverted"):
            gravar(os.path.join(GTK3, "assets", base + sufixo + ".png"), 16, 16, d)


def gerar_gresource():
    """Empacota as caixinhas +/- em gtk-3.0/gtk.gresource.

    O GTK3 estica imagens url() até a altura da linha da árvore (borradas), mas
    desenha ícones de tema de ícones no tamanho real e centralizados. Ao carregar
    o tema, o GTK3 registra o gtk.gresource da pasta gtk-3.0, e o caminho de
    recursos /org/gtk/libgtk/icons/ faz parte do tema de ícones hicolor. Assim
    o CSS acha as imagens com -gtk-icontheme("treeview-closed"), sem instalar
    nada fora do tema.
    Dependência: glib-compile-resources (pacote glib2, já vem com o GTK)."""
    nomes = ["treeview-closed", "treeview-closed-inverted",
             "treeview-opened", "treeview-opened-inverted"]
    arquivos = "".join('    <file alias="%s.png">assets/%s.png</file>\n' % (n, n) for n in nomes)
    xml = ('<?xml version="1.0" encoding="UTF-8"?>\n<gresources>\n'
           '  <gresource prefix="/org/gtk/libgtk/icons/16x16/actions">\n'
           + arquivos + '  </gresource>\n</gresources>\n')
    with tempfile.NamedTemporaryFile("w", suffix=".gresource.xml", delete=False) as f:
        f.write(xml)
    try:
        subprocess.run(["glib-compile-resources", "--sourcedir=" + GTK3,
                        "--target=" + os.path.join(GTK3, "gtk.gresource"), f.name],
                       check=True)
    finally:
        os.unlink(f.name)


def main():
    ajustar_css()
    desenhar_expansores()
    gerar_gresource()
    total = arquivos = 0
    for raiz, _, nomes in os.walk(GTK3):
        for nome in sorted(nomes):
            if nome.endswith(".png") and not os.path.islink(os.path.join(raiz, nome)):
                n = recolorir(os.path.join(raiz, nome))
                if n:
                    arquivos += 1
                    total += n
                    print("  %-45s %3d px" % (os.path.relpath(os.path.join(raiz, nome), GTK3), n))
    print("OK: %d pixels de sombra em %d imagens -> #404040" % (total, arquivos))


if __name__ == "__main__":
    main()
