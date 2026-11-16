#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Gera o tema de cursores "windows-classic-cursors" (X11) a partir da pasta I386 de um
CD original do Windows XP.

Os cursores do esquema padrão do XP ("Windows Padrão") ficam dentro do
USER32.DLL e, os de arrastar e soltar, no OLE32.DLL. O script:

  1. descompacta USER32.DL_ e OLE32.DL_ da pasta I386 (cabextract);
  2. lê os recursos de cursor das DLLs (wrestool + wincur.py);
  3. converte cada cursor em PNG nas escalas 1x, 2x e 3x (32, 64 e 96 px),
     sem suavização, mantendo o visual pixelado original;
  4. compila com o xcursorgen em Cursors/windows-classic-cursors/cursors/;
  5. cria os links simbólicos com os nomes alternativos (X11, CSS, hashes).

Os cursores gerados já vêm no projeto; o script só é preciso para gerá-los de novo.

Dependências (Arch Linux):
    sudo pacman -S --needed python cabextract icoutils xorg-xcursorgen

Uso:
    python3 Cursors/src/build.py /caminho/para/I386
"""

import os
import shutil
import struct
import subprocess
import sys
import tempfile
import zlib

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, AQUI)
import wincur  # noqa: E402

RAIZ = os.path.dirname(AQUI)                      # pasta Cursors/
BUILD = os.path.join(RAIZ, "build")               # PNGs intermediários
TEMA = os.path.join(RAIZ, "windows-classic-cursors")  # tema final
CURSORES = os.path.join(TEMA, "cursors")

ESCALAS = (1, 2, 3)
PRETO = (0, 0, 0, 255)
BRANCO = (255, 255, 255, 255)
VAZIO = (0, 0, 0, 0)

# cursor principal -> (dll, grupo de recurso, transformação)
PRINCIPAIS = {
    "default":       ("user32", 100, None),
    "text":          ("user32", 101, None),
    "vertical-text": ("user32", 101, "girar"),
    "wait":          ("user32", 102, None),
    "crosshair":     ("user32", 103, None),
    "up-arrow":      ("user32", 104, None),
    "nwse-resize":   ("user32", 105, None),
    "nesw-resize":   ("user32", 106, None),
    "ew-resize":     ("user32", 107, None),
    "ns-resize":     ("user32", 108, None),
    "move":          ("user32", 109, None),
    "not-allowed":   ("user32", 110, None),
    "progress":      ("user32", 111, None),
    "help":          ("user32", 112, None),
    "pencil":        ("user32", 113, None),
    "pointer":       ("user32", 114, None),
    "all-scroll":    ("user32", 32654, None),
    "no-drop":       ("ole32", 1, None),
    "dnd-move":      ("ole32", 2, None),
    "copy":          ("ole32", 3, None),
    "alias":         ("ole32", 4, None),
    "right_ptr":     ("user32", 100, "espelhar"),
}

# nomes alternativos (links simbólicos) -> cursor principal
APELIDOS = {
    "default": [
        "left_ptr", "arrow", "top_left_arrow", "left_arrow", "context-menu",
        "draft_large", "draft_small", "x-cursor", "X_cursor", "zoom-in", "zoom-out",
    ],
    "text": ["xterm", "ibeam"],
    "vertical-text": [],
    "wait": ["watch", "0426c94ea35c87780ff01dc239897213"],
    "crosshair": [
        "cross", "tcross", "cross_reverse", "diamond_cross", "plus", "cell",
        "target", "dotbox",
    ],
    "up-arrow": ["up_arrow", "center_ptr", "sb_up_arrow"],
    "nwse-resize": [
        "size_fdiag", "bd_double_arrow", "nw-resize", "se-resize",
        "top_left_corner", "bottom_right_corner", "ul_angle", "lr_angle",
        "c7088f0f3e6c8088236ef8e1e3e70000",
    ],
    "nesw-resize": [
        "size_bdiag", "fd_double_arrow", "ne-resize", "sw-resize",
        "top_right_corner", "bottom_left_corner", "ur_angle", "ll_angle",
        "fcf1c3c7cd4491d801f1e1c78f100000",
    ],
    "ew-resize": [
        "size_hor", "h_double_arrow", "sb_h_double_arrow", "e-resize", "w-resize",
        "left_side", "right_side", "col-resize", "split_h",
        "028006030e0e7ebffc7f7070c0600140", "14fef782d02440884392942c11205230",
    ],
    "ns-resize": [
        "size_ver", "v_double_arrow", "sb_v_double_arrow", "n-resize", "s-resize",
        "top_side", "bottom_side", "row-resize", "split_v", "double_arrow",
        "00008160000006810000408080010102", "2870a09082c103050810ffdffffe0204",
    ],
    "move": [
        "fleur", "size_all", "4498f0e0c1937ffe01fd06f973665830",
        "9081237383d90e509aa00f00170e968f", "fcf21c00b30f7e3f83fe0dfd12e71cff",
    ],
    "all-scroll": [],
    "not-allowed": [
        "circle", "crossed_circle", "forbidden", "pirate",
        "03b6e0fcb3499374a867c041f52298f0",
    ],
    "no-drop": ["dnd-no-drop", "dnd-none"],
    "progress": [
        "left_ptr_watch", "half-busy", "08e8e1c95fe2fc01f976f1e063a24ccd",
        "3ecb610c1bf2410f44200f48c40d3599", "00000000000000020006000e7e9ffc3f",
    ],
    "help": [
        "question_arrow", "whats_this", "left_ptr_help", "dnd-ask",
        "5c6cd98b3f3ebcb1f9c7f1c204630408", "d9ce0ab605698f320427677b458ad60b",
    ],
    "pencil": ["draft"],
    "pointer": [
        "hand", "hand1", "hand2", "pointing_hand", "grab", "grabbing", "openhand",
        "closedhand", "9d800788f1b08800ae810202380a0822",
        "e29285e634086352946a0e7090d73106", "5aca4d189052212118709018842178c0",
    ],
    "dnd-move": [],
    "copy": [
        "dnd-copy", "1081e37283d90000800003c07f3ef6bf",
        "6407b0e94181790501fd1e167b474872", "b66166c04f8c3109214a4fbd64a50fc8",
    ],
    "alias": [
        "link", "dnd-link", "3085a0e285430894940527032f8b26df",
        "640fb0e74195791501fd1ed57b41487f", "a2a266d0498c3104214a47bd64ab0fc8",
    ],
    "right_ptr": ["e-arrow"],
}


# ---------------------------------------------------------------------------
# Tratamento das imagens
# ---------------------------------------------------------------------------
def resolver_inversao(cur):
    """Pixels que invertem a tela (cursor de texto, mira) não existem no
    Xcursor: viram preto com 1 px de contorno branco, para continuar
    visíveis em qualquer fundo."""
    px = dict(cur["px"])
    inv = [p for p, c in px.items() if c == "inv"]
    for p in inv:
        px[p] = PRETO
    for (x, y) in inv:
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                q = (x + dx, y + dy)
                if q not in px and 0 <= q[0] < cur["w"] and 0 <= q[1] < cur["h"]:
                    px[q] = BRANCO
    return dict(cur, px=px)


def transformar(cur, modo):
    w, h = cur["w"], cur["h"]
    hx, hy = cur["hot"]
    if modo == "girar":        # 90° no sentido horário
        px = {(h - 1 - y, x): c for (x, y), c in cur["px"].items()}
        return {"w": h, "h": w, "hot": (h - 1 - hy, hx), "px": px}
    if modo == "espelhar":     # espelho horizontal
        px = {(w - 1 - x, y): c for (x, y), c in cur["px"].items()}
        return {"w": w, "h": h, "hot": (w - 1 - hx, hy), "px": px}
    return cur


def gravar_png(caminho, w, h, pixel):
    bruto = bytearray()
    for y in range(h):
        bruto += b"\x00"
        for x in range(w):
            bruto += bytes(pixel(x, y))

    def bloco(tipo, dados):
        return (struct.pack(">I", len(dados)) + tipo + dados
                + struct.pack(">I", zlib.crc32(tipo + dados) & 0xFFFFFFFF))

    with open(caminho, "wb") as f:
        f.write(b"\x89PNG\r\n\x1a\n")
        f.write(bloco(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 6, 0, 0, 0)))
        f.write(bloco(b"IDAT", zlib.compress(bytes(bruto), 9)))
        f.write(bloco(b"IEND", b""))


def gravar_cursor_png(caminho, cur, escala):
    px = cur["px"]
    gravar_png(caminho, cur["w"] * escala, cur["h"] * escala,
               lambda x, y: px.get((x // escala, y // escala), VAZIO))


def previa(caminho, cursores):
    """Folha de prévia (3x, fundo verde-azulado, hotspot em vermelho)."""
    nomes = list(cursores)
    esc, cel, col = 3, 32 * 3 + 12, 6
    lin = (len(nomes) + col - 1) // col
    pos = {}
    for i, n in enumerate(nomes):
        pos[((i % col), (i // col))] = cursores[n]

    def pixel(x, y):
        c = pos.get((x // cel, y // cel))
        lx, ly = x % cel - 6, y % cel - 6
        if c is None or not (0 <= lx < 96 and 0 <= ly < 96):
            return (192, 192, 192, 255)
        p = (lx // esc, ly // esc)
        v = c["px"].get(p)
        if v:
            return v
        return (255, 0, 0, 255) if p == tuple(c["hot"]) else (0, 128, 128, 255)
    gravar_png(caminho, col * cel, lin * cel, pixel)


# ---------------------------------------------------------------------------
# Extração da I386
# ---------------------------------------------------------------------------
def achar(i386, nome):
    """Procura um arquivo na I386 ignorando maiúsculas/minúsculas."""
    for n in os.listdir(i386):
        if n.lower() == nome.lower():
            return os.path.join(i386, n)
    sys.exit("Erro: %s não encontrado em %s" % (nome, i386))


def descompactar(arquivo, destino):
    pasta = tempfile.mkdtemp(dir=destino)
    subprocess.run(["cabextract", "-q", "-d", pasta, arquivo], check=True)
    (nome,) = os.listdir(pasta)
    return os.path.join(pasta, nome)


def main():
    if len(sys.argv) != 2:
        sys.exit("Uso: %s /caminho/para/I386" % sys.argv[0])
    i386 = sys.argv[1]
    if not os.path.isdir(i386):
        sys.exit("Erro: pasta I386 não encontrada: %s" % i386)
    for prog, pacote in (("cabextract", "cabextract"), ("wrestool", "icoutils"),
                         ("xcursorgen", "xorg-xcursorgen")):
        if not shutil.which(prog):
            sys.exit("Erro: %s não encontrado. Instale com: sudo pacman -S %s" % (prog, pacote))

    shutil.rmtree(BUILD, ignore_errors=True)
    shutil.rmtree(CURSORES, ignore_errors=True)
    os.makedirs(BUILD)
    os.makedirs(CURSORES)

    with tempfile.TemporaryDirectory() as tmp:
        dlls = {
            "user32": descompactar(achar(i386, "USER32.DL_"), tmp),
            "ole32": descompactar(achar(i386, "OLE32.DL_"), tmp),
        }
        prontos = {}
        for nome, (dll, grupo, modo) in PRINCIPAIS.items():
            cur = wincur.cursor_da_dll(dlls[dll], grupo)
            prontos[nome] = transformar(resolver_inversao(cur), modo)

    for nome, cur in prontos.items():
        hx, hy = cur["hot"]
        linhas = []
        for e in ESCALAS:
            png = "%s_%d.png" % (nome, cur["w"] * e)
            gravar_cursor_png(os.path.join(BUILD, png), cur, e)
            linhas.append("%d %d %d %s" % (cur["w"] * e, hx * e, hy * e, png))
        cfg = os.path.join(BUILD, nome + ".cfg")
        with open(cfg, "w") as f:
            f.write("\n".join(linhas) + "\n")
        subprocess.run(["xcursorgen", "-p", BUILD, cfg,
                        os.path.join(CURSORES, nome)], check=True)

    for alvo, nomes in APELIDOS.items():
        for n in nomes:
            os.symlink(alvo, os.path.join(CURSORES, n))

    with open(os.path.join(TEMA, "index.theme"), "w") as f:
        f.write("[Icon Theme]\n"
                "Name=Windows Classic\n"
                "Comment=Cursores padrão do Windows XP (user32.dll / ole32.dll)\n")

    previa(os.path.join(BUILD, "preview.png"), prontos)
    total = len(os.listdir(CURSORES))
    print("OK: %d cursores, %d entradas em %s" % (len(prontos), total, CURSORES))
    print("Prévia: %s" % os.path.join(BUILD, "preview.png"))


if __name__ == "__main__":
    main()
