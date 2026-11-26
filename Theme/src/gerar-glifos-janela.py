#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Gera os botões de janela do tema GTK3 com o símbolo já desenhado (fechar, maximizar, minimizar e
restaurar).

No GTK3 o botão da barra de título (CSD) é um GtkButton com uma GtkImage que pede
window-close-symbolic e companhia ao tema de ícones, e o CSS não consegue trocar essa imagem
(-gtk-icon-source é ignorado quando a imagem tem nome de ícone). Por isso o símbolo mudava conforme
o tema de ícones ativo. Aqui o símbolo é desenhado dentro da imagem de fundo do botão
(window_button_normal.png / window_button_pressed.png), e o gtk-windowbuttons.css esconde a
imagem do ícone com "opacity: 0".

Cada PNG tem 18x18 px, com o símbolo preto no estilo Windows Clássico. Na versão "_pressed" o
símbolo desce 1 px e vai 1 px para a direita, como no botão afundado do Windows.
Saída: Theme/windows-classic/gtk-3.0/buttons/window_button_<nome>[_pressed].png

Uso: python3 Theme/src/gerar-glifos-janela.py      (requer python-pillow)
"""
import os

from PIL import Image

AQUI = os.path.dirname(os.path.abspath(__file__))
SAIDA = os.path.join(os.path.dirname(AQUI), "windows-classic", "gtk-3.0", "buttons")
TAM = 18
PRETO = (0, 0, 0, 255)

# Cada símbolo é uma lista de retângulos (x0, y0, x1, y1) em pixels, com o canto
# superior esquerdo em (0, 0); "pos" é onde o símbolo fica no botão de 18x18.
GLIFOS = {
    # X de 8x7 com traços de 2 px
    "fechar": ("fechar", (5, 5), [(0, 0, 1, 0), (6, 0, 7, 0), (1, 1, 2, 1), (5, 1, 6, 1), (2, 2, 5, 2),
                                  (3, 3, 4, 3), (2, 4, 5, 4), (1, 5, 2, 5), (5, 5, 6, 5), (0, 6, 1, 6),
                                  (6, 6, 7, 6)]),
    # caixa de 9x9 com a borda de cima dupla
    "maximizar": ("maximizar", (4, 4), [(0, 0, 8, 1), (0, 2, 0, 8), (8, 2, 8, 8), (0, 8, 8, 8)]),
    # barra de 6x2 embaixo
    "minimizar": ("minimizar", (5, 10), [(0, 0, 5, 1)]),
    # duas caixas de 6x6 sobrepostas
    "restaurar": ("restaurar", (4, 4), [(3, 0, 8, 1), (8, 2, 8, 5), (6, 5, 8, 5),
                                        (3, 2, 3, 3),
                                        (0, 3, 5, 4), (0, 5, 0, 8), (5, 5, 5, 8), (0, 8, 5, 8)]),
}


def desenhar(nome, base, deslocamento=0):
    _, (px, py), rects = GLIFOS[nome]
    im = base.copy()
    for x0, y0, x1, y1 in rects:
        for y in range(y0, y1 + 1):
            for x in range(x0, x1 + 1):
                im.putpixel((px + x + deslocamento, py + y + deslocamento), PRETO)
    return im


if __name__ == "__main__":
    os.makedirs(SAIDA, exist_ok=True)
    normal = Image.open(os.path.join(SAIDA, "window_button_normal.png")).convert("RGBA")
    pressed = Image.open(os.path.join(SAIDA, "window_button_pressed.png")).convert("RGBA")
    for nome in GLIFOS:
        desenhar(nome, normal).save(os.path.join(SAIDA, "window_button_%s.png" % nome))
        desenhar(nome, pressed, 1).save(os.path.join(SAIDA, "window_button_%s_pressed.png" % nome))
        print("OK: window_button_%s.png e window_button_%s_pressed.png" % (nome, nome))
