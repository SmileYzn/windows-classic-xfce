# -*- coding: utf-8 -*-
"""
Leitura de cursores do Windows (recursos RT_CURSOR / RT_GROUP_CURSOR de DLLs
e arquivos .ani) em Python puro.

Cada cursor decodificado vira um dicionário:
    {"w": largura, "h": altura, "hot": (x, y), "px": {(x, y): cor}}
onde cor é uma tupla RGBA ou a string "inv" (pixel que inverte a tela,
como o cursor de texto do Windows).
"""

import struct
import subprocess


def _bits(row, bpp, w):
    """Lê 'w' valores de 'bpp' bits de uma linha de bitmap."""
    out = []
    for x in range(w):
        bit = x * bpp
        byte = row[bit // 8]
        shift = 8 - bpp - (bit % 8)
        out.append((byte >> shift) & ((1 << bpp) - 1))
    return out


def decodificar_dib(dados, hot):
    """Decodifica um DIB de ícone/cursor (BITMAPINFOHEADER + paleta + XOR + AND)."""
    (tam, w, h2, _planos, bpp) = struct.unpack_from("<IiiHH", dados, 0)
    h = h2 // 2
    ncores = struct.unpack_from("<I", dados, 32)[0] or (1 << bpp if bpp <= 8 else 0)
    pos = tam
    paleta = []
    for _ in range(ncores):
        b, g, r, _ = struct.unpack_from("<BBBB", dados, pos)
        paleta.append((r, g, b))
        pos += 4
    passo_xor = ((w * bpp + 31) // 32) * 4
    passo_and = ((w + 31) // 32) * 4
    xor = dados[pos:pos + passo_xor * h]
    pos += passo_xor * h
    andm = dados[pos:pos + passo_and * h]

    px = {}
    for y in range(h):
        linha = h - 1 - y          # bitmap gravado de baixo para cima
        mascara = _bits(andm[linha * passo_and:(linha + 1) * passo_and], 1, w)
        if bpp <= 8:
            idx = _bits(xor[linha * passo_xor:(linha + 1) * passo_xor], bpp, w)
            cores = [paleta[i] for i in idx]
        elif bpp == 32:
            cores = []
            for x in range(w):
                b, g, r, a = struct.unpack_from("<BBBB", xor, linha * passo_xor + x * 4)
                cores.append((r, g, b, a))
        else:
            raise ValueError("profundidade de cor não suportada: %d" % bpp)
        for x in range(w):
            c = cores[x]
            if bpp == 32:
                if c[3]:
                    px[(x, y)] = c
                continue
            if mascara[x] == 0:
                px[(x, y)] = c + (255,)
            elif c != (0, 0, 0):
                px[(x, y)] = "inv"
    return {"w": w, "h": h, "hot": hot, "px": px}


def decodificar_cur_recurso(dados):
    """RT_CURSOR: 2 words de hotspot + DIB."""
    hx, hy = struct.unpack_from("<HH", dados, 0)
    return decodificar_dib(dados[4:], (hx, hy))


def _wrestool(dll, tipo, nome):
    return subprocess.run(
        ["wrestool", "-x", "--raw", "--type=%d" % tipo, "--name=%s" % nome, dll],
        check=True, capture_output=True).stdout


def cursor_da_dll(dll, grupo):
    """Lê o grupo de cursores 'grupo' da DLL e devolve a imagem 32x32."""
    g = _wrestool(dll, 12, grupo)
    _res, _tipo, n = struct.unpack_from("<HHH", g, 0)
    melhor = None
    for i in range(n):
        w, h2, _pl, bpp, _sz, ident = struct.unpack_from("<HHHHIH", g, 6 + i * 14)
        cand = (w == 32, bpp, ident)
        if melhor is None or cand > melhor:
            melhor = cand
    return decodificar_cur_recurso(_wrestool(dll, 1, melhor[2]))


def _decodificar_arquivo_ico(dados):
    """Arquivo .cur/.ico completo; devolve a primeira imagem (preferindo 32px)."""
    _res, _tipo, n = struct.unpack_from("<HHH", dados, 0)
    ents = []
    for i in range(n):
        w, h, _c, _r, hx, hy, tam, ofs = struct.unpack_from("<BBBBHHII", dados, 6 + i * 16)
        ents.append(((w or 256) == 32, (hx, hy), dados[ofs:ofs + tam]))
    ents.sort(key=lambda e: not e[0])
    _, hot, dib = ents[0]
    return decodificar_dib(dib, hot)


def ler_ani(caminho):
    """Lê um .ani (RIFF ACON) e devolve [(cursor, atraso_ms)] na ordem de exibição."""
    with open(caminho, "rb") as f:
        dados = f.read()
    if dados[:4] != b"RIFF" or dados[8:12] != b"ACON":
        raise ValueError("não é um .ani: %s" % caminho)
    quadros, taxas, seq = [], None, None
    passos_padrao = 10
    pos = 12

    def blocos(ini, fim):
        p = ini
        while p + 8 <= fim:
            cid = dados[p:p + 4]
            tam = struct.unpack_from("<I", dados, p + 4)[0]
            yield cid, p + 8, tam
            p += 8 + tam + (tam & 1)

    for cid, ini, tam in blocos(pos, len(dados)):
        if cid == b"anih":
            (_cb, _nf, _ns, _cx, _cy, _bc, _np, jif, _fl) = struct.unpack_from("<9I", dados, ini)
            passos_padrao = jif
        elif cid == b"rate":
            taxas = list(struct.unpack_from("<%dI" % (tam // 4), dados, ini))
        elif cid == b"seq ":
            seq = list(struct.unpack_from("<%dI" % (tam // 4), dados, ini))
        elif cid == b"LIST" and dados[ini:ini + 4] == b"fram":
            for c2, i2, t2 in blocos(ini + 4, ini + tam):
                if c2 == b"icon":
                    quadros.append(_decodificar_arquivo_ico(dados[i2:i2 + t2]))
    ordem = seq if seq else list(range(len(quadros)))
    res = []
    for k, i in enumerate(ordem):
        jif = taxas[k] if taxas else passos_padrao
        res.append((quadros[i], round(jif * 1000 / 60)))   # 1 jiffy = 1/60 s
    return res

