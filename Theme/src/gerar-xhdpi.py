#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Gera o tema Theme/windows-classic-xhdpi (bordas xfwm4 em 2x) a partir de
Theme/windows-classic/xfwm4.

No xfwm4 4.20 as variantes HiDPI são temas separados, seguindo a convenção do
próprio XFCE ("Default-xhdpi" = 2x). Com a escala de janelas em 2x
(Configurações → Aparência → Configurações → Escala de janelas), escolha
"windows-classic-xhdpi" em Configurações → Gerenciador de janelas → Estilo.

O que o script faz:
  - amplia cada .xpm em 2x pixel a pixel (sem suavização), preservando as
    cores simbólicas ("s active_color_1" etc.) que o xfwm4 troca pelas do themerc;
  - dobra a altura dos degradês title-*-stretch.png (a largura o xfwm4 estica);
  - copia o themerc dobrando os valores em pixels (deslocamentos e bordas).

Sempre que algo mudar em xfwm4/, rode de novo:
    python3 Theme/src/gerar-xhdpi.py

Dependência: ImageMagick (sudo pacman -S --needed imagemagick), só para os PNGs.
"""

import os
import re
import shutil
import subprocess
import sys

AQUI = os.path.dirname(os.path.abspath(__file__))
TEMAS = os.path.dirname(AQUI)                     # pasta Theme/
ORIGEM = os.path.join(TEMAS, "windows-classic", "xfwm4")
DESTINO = os.path.join(TEMAS, "windows-classic-xhdpi", "xfwm4")
ESCALA = 2

# opções do themerc medidas em pixels
CHAVES_PIXEL = {
    "button_offset", "button_spacing", "maximized_offset",
    "title_horizontal_offset", "title_vertical_offset_active",
    "title_vertical_offset_inactive", "frame_border_top",
    "frame_border_bottom", "frame_border_left", "frame_border_right",
    "title_shadow_offset",
}


def ampliar_xpm(texto):
    """Amplia um XPM em ESCALA x, mantendo cabeçalho e tabela de cores."""
    linhas = texto.split("\n")
    strings = [i for i, l in enumerate(linhas) if l.lstrip().startswith('"')]
    ih = strings[0]
    m = re.match(r'(\s*)"(\d+) (\d+) (\d+) (\d+)(.*)"(.*)$', linhas[ih])
    ind, w, h, nc, cpp, resto, fim = m.groups()
    w, h, nc, cpp = int(w), int(h), int(nc), int(cpp)
    linhas[ih] = '%s"%d %d %d %d%s"%s' % (ind, w * ESCALA, h * ESCALA, nc, cpp, resto, fim)

    pixels = strings[1 + nc:1 + nc + h]
    novas = []
    for k, i in enumerate(pixels):
        l = linhas[i]
        a, b = l.index('"'), l.rindex('"')
        conteudo = l[a + 1:b]
        sufixo = l[b + 1:]
        px = [conteudo[j:j + cpp] for j in range(0, len(conteudo), cpp)]
        larga = "".join(p * ESCALA for p in px)
        for r in range(ESCALA):
            ultima = (k == len(pixels) - 1 and r == ESCALA - 1)
            s = sufixo if ultima else ","
            if not ultima and sufixo.strip().startswith("}"):
                s = ","
            novas.append('%s"%s"%s' % (l[:a], larga, s))
    ini, fim_i = pixels[0], pixels[-1]
    return "\n".join(linhas[:ini] + novas + linhas[fim_i + 1:])


def ampliar_themerc(texto):
    saida = []
    for l in texto.split("\n"):
        m = re.match(r"^(\w+)=(-?\d+)\s*$", l)
        if m and m.group(1) in CHAVES_PIXEL:
            l = "%s=%d" % (m.group(1), int(m.group(2)) * ESCALA)
        saida.append(l)
    return "\n".join(saida).replace(
        "# Nome: Windows Classic (xfwm4)",
        "# Nome: Windows Classic (xfwm4, HiDPI 2x)\n"
        "# ARQUIVO GERADO por Theme/src/gerar-xhdpi.py: edite windows-classic/xfwm4/themerc.", 1)


def main():
    if not os.path.isdir(ORIGEM):
        sys.exit("Erro: pasta não encontrada: %s" % ORIGEM)
    shutil.rmtree(DESTINO, ignore_errors=True)
    os.makedirs(DESTINO)
    n = 0
    for nome in sorted(os.listdir(ORIGEM)):
        src = os.path.join(ORIGEM, nome)
        dst = os.path.join(DESTINO, nome)
        if nome.endswith(".xpm"):
            with open(src) as f:
                conteudo = ampliar_xpm(f.read())
            with open(dst, "w") as f:
                f.write(conteudo)
        elif nome.endswith(".png"):
            if not shutil.which("magick"):
                sys.exit("Erro: ImageMagick não encontrado: sudo pacman -S --needed imagemagick")
            subprocess.run(["magick", src, "-filter", "point",
                            "-resize", "100%%x%d%%" % (ESCALA * 100), dst], check=True)
        elif nome == "themerc":
            with open(src) as f:
                conteudo = ampliar_themerc(f.read())
            with open(dst, "w") as f:
                f.write(conteudo)
        else:
            shutil.copy2(src, dst)
        n += 1
    print("OK: %d arquivos gerados em %s" % (n, DESTINO))


if __name__ == "__main__":
    main()
