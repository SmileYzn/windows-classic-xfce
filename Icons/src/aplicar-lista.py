#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Monta o tema Icons/windows-classic-icons a partir da lista de ícones
(Icons/windows-classic-icons.list, exportada e editada pelo Icons/mapa.html).

Formato da lista (separado por TAB; linhas com # são comentários):

    contexto/nome    origem    tamanhos    observação

  origem:   xp:<nome>                - ícone da galeria XP (Icons/build/xp-icons/<N>x<N>/<nome>.png)
            i386:<arquivo>#<grupo>  - ícone da galeria da I386 (Icons/build/i386)
            /caminho/arquivo.png     - um PNG seu, redimensionado para cada tamanho
            (SVG só funciona se o tema voltar a ter as pastas scalable/<contexto>)
  tamanhos: 16,22,24,32,48 (os que existirem na origem; nos ícones das galerias XP e
            I386 não há redimensionamento: um tamanho que não existe lá é pulado)

O tema é refeito do zero a cada execução: os PNG e SVG das pastas do tema são
apagados e gravados de novo conforme a lista (o index.theme e os .gitkeep ficam).
Quando a mesma imagem serve a vários nomes na mesma pasta, os nomes seguintes
viram links simbólicos para o primeiro.

Para evitar apagar o tema por engano (por exemplo, com uma lista exportada pela metade),
o script recusa uma lista que removeria mais de LIMITE nomes que o tema tem hoje; nesse
caso, confira a lista ou rode com --forcar.

Uso:
    python3 Icons/src/extrair-i386.py /caminho/para/I386     # uma vez (galeria)
    python3 Icons/src/aplicar-lista.py [lista] [--forcar]
    python3 Icons/src/mapa.py                                 # para conferir

Dependência para PNG próprios (redimensionar): sudo pacman -S --needed imagemagick
"""

import configparser
import os
import shutil
import subprocess
import sys

AQUI = os.path.dirname(os.path.abspath(__file__))
ICONS = os.path.dirname(AQUI)
TEMA = os.path.join(ICONS, "windows-classic-icons")
I386 = os.path.join(ICONS, "build", "i386")
XP_ICONS = os.path.join(ICONS, "build", "xp-icons")
LISTA = os.path.join(ICONS, "windows-classic-icons.list")
LIMITE = 10                     # nomes que podem sair do tema sem --forcar


def pastas_do_tema():
    """{(contexto, tamanho): pasta}, com tamanho = int ou "scalable"."""
    cp = configparser.ConfigParser(interpolation=None, strict=False)
    cp.optionxform = str
    cp.read(os.path.join(TEMA, "index.theme"), encoding="utf-8")
    out = {}
    for d in cp["Icon Theme"]["Directories"].split(","):
        tam = "scalable" if cp[d].get("Type") == "Scalable" else int(cp[d]["Size"])
        out[(d.split("/")[1], tam)] = d
    return out


def ler_lista(caminho):
    itens = []
    with open(caminho, encoding="utf-8") as f:
        for n, linha in enumerate(f, 1):
            linha = linha.rstrip("\n")
            if not linha.strip() or linha.lstrip().startswith("#"):
                continue
            partes = linha.split("\t")
            if len(partes) < 2 or "/" not in partes[0]:
                sys.exit("%s:%d: esperado 'contexto/nome<TAB>origem<TAB>tamanhos'" % (caminho, n))
            ctx, nome = partes[0].split("/", 1)
            tams = [t.strip() for t in (partes[2] if len(partes) > 2 else "").split(",") if t.strip()]
            itens.append((n, ctx, nome, partes[1].strip(), [t if t == "scalable" else int(t) for t in tams]))
    return itens


def limpar(pastas):
    apagados = 0
    for d in set(pastas.values()):
        p = os.path.join(TEMA, d)
        for f in os.listdir(p):
            if f.endswith((".png", ".svg")):
                os.remove(os.path.join(p, f))
                apagados += 1
    return apagados


def nomes_no_tema(pastas):
    nomes = set()
    for d in set(pastas.values()):
        for f in os.listdir(os.path.join(TEMA, d)):
            if f.endswith((".png", ".svg")):
                nomes.add(os.path.splitext(f)[0])
    return nomes


def main():
    args = [a for a in sys.argv[1:] if a != "--forcar"]
    forcar = "--forcar" in sys.argv[1:]
    lista = args[0] if args else LISTA
    pastas = pastas_do_tema()
    itens = ler_lista(lista)
    saem = nomes_no_tema(pastas) - {nome for _, _, nome, _, _ in itens}
    if len(saem) > LIMITE and not forcar:
        sys.exit("A lista %s removeria %d nomes que o tema tem hoje (ex.: %s).\n"
                 "Nada foi alterado. Confira a lista (uma exportação do mapa.html feita antes\n"
                 "de abrir a lista do projeto sai incompleta) ou rode de novo com --forcar."
                 % (lista, len(saem), ", ".join(sorted(saem)[:5])))
    if any(o.startswith("i386:") for _, _, _, o, _ in itens) and not os.path.isdir(I386):
        sys.exit("A galeria da I386 não existe. Rode antes:\n"
                 "    python3 Icons/src/extrair-i386.py /caminho/para/I386")
    if any(o.startswith("xp:") for _, _, _, o, _ in itens) and not os.path.isdir(XP_ICONS):
        sys.exit("A galeria XP não existe: falta a pasta %s" % XP_ICONS)
    apagados = limpar(pastas)

    gravados = links = 0
    avisos = []
    feitos = {}                     # (pasta, origem real) -> nome do arquivo já gravado
    for n, ctx, nome, origem, tams in itens:
        if not any(c == ctx for c, _ in pastas):
            avisos.append("linha %d: contexto desconhecido '%s'" % (n, ctx))
            continue
        if origem.endswith(".svg"):
            tams = ["scalable"]
        for tam in tams:
            pasta = pastas.get((ctx, tam))
            if not pasta:
                avisos.append("linha %d: o tema não tem a pasta %s/%s" % (n, tam, ctx))
                continue
            if origem.startswith("i386:"):
                arq, grupo = origem[5:].split("#", 1)
                fonte = os.path.join(I386, arq, "%s-%s.png" % (grupo, tam))
                if not os.path.isfile(fonte):
                    avisos.append("linha %d: %s não tem %s px" % (n, origem, tam))
                    continue
            elif origem.startswith("xp:"):
                fonte = os.path.join(XP_ICONS, "%sx%s" % (tam, tam), origem[3:] + ".png")
                if tam == "scalable" or not os.path.isfile(fonte):
                    avisos.append("linha %d: %s não tem %s px" % (n, origem, tam))
                    continue
            else:
                fonte = os.path.expanduser(origem)
                if not os.path.isfile(fonte):
                    avisos.append("linha %d: arquivo não encontrado: %s" % (n, origem))
                    continue
            ext = ".svg" if fonte.endswith(".svg") else ".png"
            destino = os.path.join(TEMA, pasta, nome + ext)
            chave = (pasta, os.path.realpath(fonte), tam)
            if chave in feitos and feitos[chave] != nome + ext:
                os.symlink(feitos[chave], destino)
                links += 1
                continue
            if ext == ".svg" or origem.startswith(("i386:", "xp:")):
                shutil.copyfile(fonte, destino)
            else:
                subprocess.run(["magick", fonte, "-background", "none", "-resize", "%dx%d" % (tam, tam),
                                "-gravity", "center", "-extent", "%dx%d" % (tam, tam),
                                "PNG32:" + destino], check=True)
            feitos[chave] = nome + ext
            gravados += 1

    for a in avisos:
        print("aviso:", a)
    print("OK: %d nomes na lista; %d imagens gravadas e %d links em %s (%d arquivos antigos apagados)"
          % (len(itens), gravados, links, TEMA, apagados))


if __name__ == "__main__":
    main()
