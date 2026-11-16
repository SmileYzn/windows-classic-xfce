#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Extrai da pasta I386 do Windows XP a marca do Explorer usada pelo tema GTK:

  SHELL32.DLL   (bitmap 240): marca do Explorer do XP (bandeira em fundo branco),
                50 quadros de 22x22 em cores verdadeiras
      -> gtk-3.0/assets/throbber/throbber_f0..f49.png  (bandeira tremulando)
      -> gtk-3.0/assets/status_badge_xp.png  (quadro 0, bandeira parada)

As imagens geradas já vêm no projeto; o script só é preciso para extraí-las de novo.

Dependências (Arch Linux):
    sudo pacman -S --needed cabextract icoutils imagemagick
Uso:
    python3 Theme/src/extrair-xp.py /caminho/para/I386
"""

import os
import shutil
import subprocess
import sys
import tempfile

AQUI = os.path.dirname(os.path.abspath(__file__))
ASSETS = os.path.join(os.path.dirname(AQUI), "windows-classic", "gtk-3.0", "assets")

# Tira vertical de 22x22 (241 = 26 px, 242 = 38 px; 245-247 são as versões de 256 cores).
# Os bitmaps 304-306 da browseui.dll são a marca antiga, do Windows 2000, em fundo preto.
THROBBER = 240
LADO = 22


def achar(i386, nome):
    for n in os.listdir(i386):
        if n.lower() == nome.lower():
            return os.path.join(i386, n)
    sys.exit("Erro: %s não encontrado em %s" % (nome, i386))


def descompactar(arquivo, destino):
    pasta = tempfile.mkdtemp(dir=destino)
    subprocess.run(["cabextract", "-q", "-d", pasta, arquivo], check=True)
    (nome,) = os.listdir(pasta)
    return os.path.join(pasta, nome)


def bitmap(dll, nome, saida):
    subprocess.run(["wrestool", "-x", "--type=2", "--name=%d" % nome, dll, "-o", saida],
                   check=True)


def main():
    if len(sys.argv) != 2 or not os.path.isdir(sys.argv[1]):
        sys.exit("Uso: %s /caminho/para/I386" % sys.argv[0])
    for prog, pacote in (("cabextract", "cabextract"), ("wrestool", "icoutils"),
                         ("magick", "imagemagick")):
        if not shutil.which(prog):
            sys.exit("Erro: %s não encontrado. Instale com: sudo pacman -S %s" % (prog, pacote))
    i386 = sys.argv[1]
    os.makedirs(os.path.join(ASSETS, "throbber"), exist_ok=True)

    with tempfile.TemporaryDirectory() as tmp:
        shell32 = descompactar(achar(i386, "SHELL32.DL_"), tmp)

        bmp = os.path.join(tmp, "throbber.bmp")
        bitmap(shell32, THROBBER, bmp)
        quadros = os.path.join(tmp, "quadro_%d.png")
        subprocess.run(["magick", bmp, "-crop", "%dx%d" % (LADO, LADO), "+repage",
                        "PNG32:" + quadros], check=True)
        n = 0
        while os.path.exists(quadros % n):
            shutil.copy(quadros % n, os.path.join(ASSETS, "throbber", "throbber_f%d.png" % n))
            n += 1
        shutil.copy(quadros % 0, os.path.join(ASSETS, "status_badge_xp.png"))

    print("OK: %d quadros da marca do Explorer em %s" % (n, ASSETS))


if __name__ == "__main__":
    main()
