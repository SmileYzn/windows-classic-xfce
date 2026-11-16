#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Extrai os ícones dos arquivos do Windows XP (pasta I386 do CD) para uma galeria
usada pelo Icons/mapa.html na hora de escolher ícones para os nomes que faltam.

Para cada arquivo da lista ARQUIVOS o script:

  1. descompacta o arquivo (FOO.DL_ -> foo.dll) com o cabextract ou o 7z;
     os que não estão soltos na I386 são procurados dentro do SP3.CAB;
  2. lê os recursos RT_GROUP_ICON / RT_ICON direto do executável (Python puro);
  3. grava cada tamanho disponível como PNG, escolhendo a versão com mais cores:
     Icons/build/i386/<arquivo>/<grupo>-<tamanho>.png

No fim grava Icons/build/i386/indice.json, lido pelo Icons/src/mapa.py.
Os ícones extraídos não vão para o repositório (Icons/build/ está no .gitignore).

Dependências (Arch Linux), uma das duas:
    sudo pacman -S --needed cabextract     (ou)     sudo pacman -S --needed 7zip

Uso:
    python3 Icons/src/extrair-i386.py /caminho/para/I386
"""

import json
import os
import shutil
import struct
import subprocess
import sys
import tempfile
import zlib

AQUI = os.path.dirname(os.path.abspath(__file__))
SAIDA = os.path.join(os.path.dirname(AQUI), "build", "i386")

# Arquivos do XP com mais ícones úteis para um tema (pastas, unidades, dispositivos,
# painel de controle, correio, rede, segurança, energia, acessórios e jogos).
ARQUIVOS = """
shell32.dll explorer.exe moricons.dll setupapi.dll pifmgr.dll mydocs.dll
mmsys.cpl netshell.dll sysdm.cpl main.cpl timedate.cpl desk.cpl inetcpl.cpl access.cpl
intl.cpl powercfg.cpl appwiz.cpl hdwwiz.cpl joy.cpl telephon.cpl ncpa.cpl nusrmgr.cpl
wuaucpl.cpl wscui.cpl irprops.cpl
wiashext.dll msgina.dll shdocvw.dll browseui.dll wab32res.dll msoeres.dll fontext.dll
stobject.dll modemui.dll printui.dll wmploc.dll cdfview.dll url.dll
dsuiext.dll mmcndmgr.dll zipfldr.dll hhctrl.ocx comres.dll odbcint.dll certmgr.dll
cryptui.dll themeui.dll cscui.dll devmgr.dll dmdskres.dll filemgmt.dll hnetwiz.dll
mshtml.dll netplwiz.dll powrprof.dll rasdlg.dll sti.dll wiadefui.dll wmpui.dll hypertrm.dll
notepad.exe calc.exe mspaint.exe charmap.exe cmd.exe taskmgr.exe regedit.exe winhlp32.exe
wordpad.exe sndvol32.exe sndrec32.exe dxdiag.exe mobsync.exe msconfig.exe magnify.exe
osk.exe narrator.exe utilman.exe mstsc.exe msimn.exe wmplayer.exe moviemk.exe progman.exe
sol.exe winmine.exe freecell.exe mshearts.exe spider.exe dialer.exe eudcedit.exe
hypertrm.exe iexplore.exe mmc.exe msinfo32.exe helpctr.exe ntbackup.exe systray.exe
""".split()

RT_ICON, RT_GROUP_ICON = 3, 14


# ---------------------------------------------------------------- descompactação

def achar(i386, nome):
    """Procura FOO.DLL ou FOO.DL_ na I386 (sem diferenciar maiúsculas)."""
    comprimido = nome[:-1] + "_"
    for n in os.listdir(i386):
        if n.lower() in (nome, comprimido):
            return os.path.join(i386, n)
    return None


def descompactar(arquivo, destino, membro=None):
    """Extrai um arquivo comprimido (ou um membro de um .CAB) e devolve o caminho."""
    pasta = tempfile.mkdtemp(dir=destino)
    if shutil.which("cabextract"):
        cmd = ["cabextract", "-q", "-d", pasta] + (["-F", membro] if membro else []) + [arquivo]
    else:
        cmd = ["7z", "e", "-y", "-bso0", "-bsp0", "-o" + pasta, arquivo] + ([membro] if membro else [])
    subprocess.run(cmd, check=True, stderr=subprocess.DEVNULL)
    nomes = os.listdir(pasta)
    return os.path.join(pasta, nomes[0]) if nomes else None


def obter(i386, nome, tmp):
    """Devolve o caminho de 'nome' já descompactado, ou None se não existir."""
    p = achar(i386, nome)
    if p and p.endswith("_"):
        return descompactar(p, tmp)
    if p:
        return p
    sp3 = achar(i386, "sp3.cab")
    if sp3:
        return descompactar(sp3, tmp, nome)
    return None


# ---------------------------------------------------------------- recursos PE

def recursos(dados):
    """Lê a seção de recursos de um PE. Devolve {tipo: {nome: bytes}} (1º idioma)."""
    pe = struct.unpack_from("<I", dados, 0x3C)[0]
    if dados[pe:pe + 4] != b"PE\0\0":
        return {}
    nsec, = struct.unpack_from("<H", dados, pe + 6)
    tam_opc, = struct.unpack_from("<H", dados, pe + 20)
    opc = pe + 24
    magia, = struct.unpack_from("<H", dados, opc)
    dirs = opc + (96 if magia == 0x10B else 112)
    rva_rec, tam_rec = struct.unpack_from("<II", dados, dirs + 2 * 8)
    if not rva_rec:
        return {}
    secoes = []
    for i in range(nsec):
        s = opc + tam_opc + i * 40
        vtam, va, rtam, rptr = struct.unpack_from("<IIII", dados, s + 8)
        secoes.append((va, max(vtam, rtam), rptr))

    def ofs(rva):
        for va, tam, rptr in secoes:
            if va <= rva < va + tam:
                return rva - va + rptr
        raise ValueError("RVA fora das seções")

    base = ofs(rva_rec)

    def entradas(pos):
        nnome, nid = struct.unpack_from("<HH", dados, pos + 12)
        for i in range(nnome + nid):
            nome, alvo = struct.unpack_from("<II", dados, pos + 16 + i * 8)
            if nome & 0x80000000:
                p = base + (nome & 0x7FFFFFFF)
                n, = struct.unpack_from("<H", dados, p)
                nome = dados[p + 2:p + 2 + n * 2].decode("utf-16-le").lower()
            yield nome, alvo

    out = {}
    for tipo, a1 in entradas(base):
        if tipo not in (RT_ICON, RT_GROUP_ICON) or not a1 & 0x80000000:
            continue
        for nome, a2 in entradas(base + (a1 & 0x7FFFFFFF)):
            if not a2 & 0x80000000:
                continue
            _idioma, a3 = next(entradas(base + (a2 & 0x7FFFFFFF)))
            rva, tam = struct.unpack_from("<II", dados, base + a3)
            out.setdefault(tipo, {})[nome] = dados[ofs(rva):ofs(rva) + tam]
    return out


# ---------------------------------------------------------------- imagens

def bits(linha, bpp, w):
    out = []
    for x in range(w):
        b = x * bpp
        out.append((linha[b // 8] >> (8 - bpp - b % 8)) & ((1 << bpp) - 1))
    return out


def dib_para_rgba(d):
    """Converte o DIB de um RT_ICON (1/4/8/24/32 bits + máscara AND) em RGBA."""
    tam, w, h2, _pl, bpp = struct.unpack_from("<IiiHH", d, 0)
    h = h2 // 2
    ncores = struct.unpack_from("<I", d, 32)[0] or (1 << bpp if bpp <= 8 else 0)
    pos = tam
    pal = [(d[pos + i * 4 + 2], d[pos + i * 4 + 1], d[pos + i * 4]) for i in range(ncores)]
    pos += ncores * 4
    pxor = ((w * bpp + 31) // 32) * 4
    pand = ((w + 31) // 32) * 4
    xor = d[pos:pos + pxor * h]
    andm = d[pos + pxor * h:pos + pxor * h + pand * h]
    # ícones de 32 bits com alfa zerado usam só a máscara AND
    usa_alfa = bpp == 32 and any(xor[i] for i in range(3, len(xor), 4))
    rgba = bytearray(w * h * 4)
    for y in range(h):
        ly = h - 1 - y                          # o DIB é gravado de baixo para cima
        linha = xor[ly * pxor:(ly + 1) * pxor]
        mask = bits(andm[ly * pand:(ly + 1) * pand], 1, w) if len(andm) >= (ly + 1) * pand else [0] * w
        if bpp <= 8:
            cores = [pal[i] if i < len(pal) else (0, 0, 0) for i in bits(linha, bpp, w)]
        elif bpp == 24:
            cores = [(linha[x * 3 + 2], linha[x * 3 + 1], linha[x * 3]) for x in range(w)]
        elif bpp == 32:
            cores = [(linha[x * 4 + 2], linha[x * 4 + 1], linha[x * 4], linha[x * 4 + 3]) for x in range(w)]
        else:
            raise ValueError("profundidade não suportada: %d" % bpp)
        for x in range(w):
            c = cores[x]
            if usa_alfa:
                a = c[3]
            else:
                a = 0 if mask[x] else 255
            i = (y * w + x) * 4
            rgba[i:i + 4] = bytes((c[0], c[1], c[2], a))
    return w, h, bytes(rgba)


def gravar_png(caminho, w, h, rgba):
    def bloco(tipo, dados):
        return (struct.pack(">I", len(dados)) + tipo + dados
                + struct.pack(">I", zlib.crc32(tipo + dados) & 0xFFFFFFFF))
    bruto = b"".join(b"\0" + rgba[y * w * 4:(y + 1) * w * 4] for y in range(h))
    with open(caminho, "wb") as f:
        f.write(b"\x89PNG\r\n\x1a\n")
        f.write(bloco(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 6, 0, 0, 0)))
        f.write(bloco(b"IDAT", zlib.compress(rgba and bruto, 9)))
        f.write(bloco(b"IEND", b""))


def extrair(caminho, destino):
    """Grava os ícones de um executável. Devolve [{grupo, tamanhos}]."""
    with open(caminho, "rb") as f:
        rec = recursos(f.read())
    icones = rec.get(RT_ICON, {})
    grupos = []
    for grupo, g in sorted(rec.get(RT_GROUP_ICON, {}).items(), key=lambda kv: (isinstance(kv[0], str), kv[0])):
        _r, _t, n = struct.unpack_from("<HHH", g, 0)
        melhor = {}                              # tamanho -> (bits, id)
        for i in range(n):
            w, h, _c, _rs, _pl, bpp, _tam, ident = struct.unpack_from("<BBBBHHIH", g, 6 + i * 14)
            w = w or 256
            if w != (h or 256) or ident not in icones:
                continue
            if w not in melhor or bpp > melhor[w][0]:
                melhor[w] = (bpp, ident)
        feitos = []
        for tam, (_bpp, ident) in sorted(melhor.items()):
            dados = icones[ident]
            arq = os.path.join(destino, "%s-%d.png" % (grupo, tam))
            try:
                if dados[:8] == b"\x89PNG\r\n\x1a\n":
                    with open(arq, "wb") as f:
                        f.write(dados)
                else:
                    w, h, rgba = dib_para_rgba(dados)
                    gravar_png(arq, w, h, rgba)
                feitos.append(tam)
            except (ValueError, struct.error, IndexError):
                pass
        if feitos:
            grupos.append({"grupo": str(grupo), "tamanhos": feitos})
    return grupos


def main():
    if len(sys.argv) != 2 or not os.path.isdir(sys.argv[1]):
        sys.exit("Uso: %s /caminho/para/I386" % sys.argv[0])
    if not (shutil.which("cabextract") or shutil.which("7z")):
        sys.exit("Erro: instale o cabextract ou o 7z:  sudo pacman -S --needed cabextract")
    i386 = sys.argv[1]
    if os.path.isdir(SAIDA):
        shutil.rmtree(SAIDA)
    indice = []
    with tempfile.TemporaryDirectory() as tmp:
        for nome in ARQUIVOS:
            exe = obter(i386, nome, tmp)
            if not exe:
                print("  não encontrado: %s" % nome)
                continue
            destino = os.path.join(SAIDA, nome)
            os.makedirs(destino)
            grupos = extrair(exe, destino)
            if not grupos:
                os.rmdir(destino)
                continue
            indice.append({"arquivo": nome, "grupos": grupos})
            print("  %-14s %4d ícones" % (nome, len(grupos)))
    with open(os.path.join(SAIDA, "indice.json"), "w", encoding="utf-8") as f:
        json.dump(indice, f, ensure_ascii=False)
    total = sum(len(a["grupos"]) for a in indice)
    print("OK: %d ícones de %d arquivos em %s" % (total, len(indice), SAIDA))


if __name__ == "__main__":
    main()
