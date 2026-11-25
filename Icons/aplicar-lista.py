#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Monta o tema Icons/windows-classic-icons a partir da lista de ícones
(Icons/windows-classic-icons.list, exportada e editada pelo Icons/mapa.html).

Formato da lista (separado por TAB; linhas com # são comentários):

    contexto/nome    origem    tamanhos    observação

  origem:   xp:<nome>                - ícone da galeria XP (Icons/xp-icons/<N>x<N>/<nome>.png)
            /caminho/arquivo.png     - um PNG seu, redimensionado para cada tamanho
            (SVG só funciona se o tema voltar a ter as pastas scalable/<contexto>)
  tamanhos: 16,22,24,32,36,48,64,96,128 (os que existirem na origem; nos ícones da galeria XP
            não há redimensionamento: um tamanho que não existe lá é pulado)

O tema é refeito do zero a cada execução: os PNG e SVG das pastas do tema são
apagados e gravados de novo conforme a lista (o index.theme e os .gitkeep ficam).
Quando a mesma imagem serve a vários nomes na mesma pasta, os nomes seguintes recebem uma
cópia do arquivo (o tema não usa links simbólicos).

Para evitar apagar o tema por engano, o script não altera nada (a não ser com --forcar) se:
  - a lista removeria mais de LIMITE nomes que o tema tem hoje (por exemplo, uma lista
    exportada pela metade);
  - algum nome da lista ficaria sem nenhuma imagem, porque a origem não existe (por exemplo,
    um ícone que não está na galeria XP).

Uso:
    python3 Icons/aplicar-lista.py [lista] [--forcar]
    python3 Icons/mapa.py                                 # para conferir

Os tamanhos e pastas do tema vêm do index.theme (gerado por Icons/gerar-index.py).

Dependência para PNG próprios (redimensionar): sudo pacman -S --needed imagemagick
"""

import configparser
import os
import shutil
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor

AQUI = os.path.dirname(os.path.abspath(__file__))
ICONS = AQUI                    # pasta Icons/
TEMA = os.path.join(ICONS, "windows-classic-icons")
XP_ICONS = os.path.join(ICONS, "xp-icons")
LISTA = os.path.join(ICONS, "windows-classic-icons.list")
LIMITE = 10                     # nomes que podem sair do tema sem --forcar

# Margem transparente nos ícones de alguns contextos. No XP os ícones de barra de ferramentas
# preenchem a imagem toda; nos temas modernos (Papirus, elementary) o desenho ocupa só uma parte
# do quadrado, e por isso parecem menores nas barras. Valor = % do quadrado que o desenho ocupa
# (100 = sem margem). Para testar outros valores sem editar o script:
#     REDUCAO_ICONES="actions=70,status=80" python3 Icons/aplicar-lista.py
REDUCAO = {"actions": 75}
# Nomes (prefixos) que nunca recebem margem, mesmo em contextos reduzidos. Os botões grandes do
# diálogo de sair da sessão (xfsm-*) ficam com tamanhos iguais ao xfsm-logout, que é de "apps".
SEM_REDUCAO = ("xfsm-",)
if os.environ.get("REDUCAO_ICONES") is not None:
    REDUCAO = {k: int(v) for k, v in (x.split("=") for x in os.environ["REDUCAO_ICONES"].split(",") if x)}


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


def achar_fonte(origem, tam):
    """(caminho da imagem de origem para o tamanho, ou None; motivo quando não há)."""
    if origem.startswith("xp:"):
        fonte = os.path.join(XP_ICONS, "%sx%s" % (tam, tam), origem[3:] + ".png")
        if tam != "scalable" and os.path.isfile(fonte):
            return fonte, ""
        return None, "%s não tem %s px" % (origem, tam)
    fonte = os.path.expanduser(origem)
    return (fonte, "") if os.path.isfile(fonte) else (None, "arquivo não encontrado: %s" % origem)


def sem_imagem(itens, pastas):
    """Itens da lista que não teriam nenhuma imagem gravada (nenhuma origem encontrada)."""
    out = []
    for n, ctx, nome, origem, tams in itens:
        tams = ["scalable"] if origem.endswith(".svg") else tams
        if not any(pastas.get((ctx, t)) and achar_fonte(origem, t)[0] for t in tams):
            out.append((n, nome, origem))
    return out


def gravar_reduzido(fonte, origem, destino, tam, pct):
    """Grava o PNG ocupando pct% do quadrado tam x tam, centralizado e com fundo transparente.
    Para ícones da galeria XP reduz a partir do PNG de 128 px (mais nítido que reduzir o de tam px
    e bem mais rápido que ler o de 1024 px)."""
    interno = max(1, round(tam * pct / 100))
    if origem.startswith("xp:"):
        grande = os.path.join(XP_ICONS, "128x128", origem[3:] + ".png")
        if os.path.isfile(grande):
            fonte = grande
    subprocess.run(["magick", "-quiet", fonte, "-filter", "Lanczos", "-resize", "%dx%d" % (interno, interno),
                    "-background", "none", "-gravity", "center", "-extent", "%dx%d" % (tam, tam),
                    "-strip", "PNG32:" + destino], check=True)


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
    if any(o.startswith("xp:") for _, _, _, o, _ in itens) and not os.path.isdir(XP_ICONS):
        sys.exit("A galeria XP não existe: falta a pasta %s" % XP_ICONS)
    # Nomes que ficariam sem imagem (ex.: a origem não existe). Como o tema é
    # refeito do zero, eles sumiriam do tema; por isso nada é alterado sem --forcar.
    vazios = sem_imagem(itens, pastas)
    if vazios and not forcar:
        sys.exit("%d nomes da lista ficariam sem nenhuma imagem (a origem não existe):\n%s\n"
                 "Nada foi alterado. Confira as origens ou rode com --forcar para aplicar mesmo assim."
                 % (len(vazios), "\n".join("    linha %d: %s  (%s)" % v for v in vazios[:20])
                    + ("\n    ..." if len(vazios) > 20 else "")))
    apagados = limpar(pastas)

    gravados = copias = 0
    iguais = []                     # (arquivo já gravado, destino): cópias feitas no fim
    avisos = []
    feitos = {}                     # (pasta, origem real) -> nome do arquivo já gravado
    reduzir = []                    # redimensionamentos pendentes (rodam em paralelo no fim)
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
            fonte, motivo = achar_fonte(origem, tam)
            if not fonte:
                avisos.append("linha %d: %s" % (n, motivo))
                continue
            ext = ".svg" if fonte.endswith(".svg") else ".png"
            destino = os.path.join(TEMA, pasta, nome + ext)
            pct = None if nome.startswith(SEM_REDUCAO) else REDUCAO.get(ctx)
            chave = (pasta, os.path.realpath(fonte), tam, pct)
            if chave in feitos and feitos[chave] != nome + ext:
                iguais.append((os.path.join(TEMA, pasta, feitos[chave]), destino))
                copias += 1
                continue
            if pct and pct < 100 and ext == ".png":
                reduzir.append((fonte, origem, destino, tam, pct))
            elif ext == ".svg" or origem.startswith("xp:"):
                shutil.copyfile(fonte, destino)
            else:
                subprocess.run(["magick", fonte, "-background", "none", "-resize", "%dx%d" % (tam, tam),
                                "-gravity", "center", "-extent", "%dx%d" % (tam, tam),
                                "PNG32:" + destino], check=True)
            feitos[chave] = nome + ext
            gravados += 1

    if reduzir:
        with ThreadPoolExecutor(max_workers=os.cpu_count() or 2) as ex:
            list(ex.map(lambda j: gravar_reduzido(*j), reduzir))
    for fonte, destino in iguais:
        shutil.copyfile(fonte, destino)

    for a in avisos:
        print("aviso:", a)
    print("OK: %d nomes na lista; %d imagens gravadas e %d cópias de imagens iguais em %s (%d arquivos antigos apagados)"
          % (len(itens), gravados, copias, TEMA, apagados))


if __name__ == "__main__":
    main()
