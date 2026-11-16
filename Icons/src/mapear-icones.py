#!/usr/bin/env python3
"""
Mapeador do tema de ícones Icons/windows-classic: análise e inclusão manual de ícones.

Uso:
    python3 Icons/src/mapear-icones.py verificar [--corrigir]
        Confere a estrutura: pastas fora do Directories= do index.theme (o GTK não as vê),
        nomes com espaço (inválidos; impedem o gtk-update-icon-cache de gerar o cache),
        arquivos que não são ícones, links quebrados, PNG com tamanho diferente do da pasta
        e cache desatualizado.
        --corrigir declara as pastas que faltam, troca espaços por hífen nos nomes e refaz
        o cache.

    python3 Icons/src/mapear-icones.py relatorio [--referencia TEMA ...]
        Classifica os nomes de ícones que o XFCE pede e gera Icons/relatorio-icones.html,
        com miniaturas (do tema ou, para os que faltam, da referência) e filtros.

    python3 Icons/src/mapear-icones.py faltando [--csv ARQUIVO]
        Lista os nomes que faltam (os pedidos por aplicativos instalados primeiro).

    python3 Icons/src/mapear-icones.py procurar TEXTO
        Ícones do tema cujo nome contém TEXTO, com os tamanhos (para achar um parecido).

    python3 Icons/src/mapear-icones.py apelido NOVO EXISTENTE
        Cria NOVO como link para EXISTENTE em todas as pastas onde EXISTENTE existe.

    python3 Icons/src/mapear-icones.py adicionar NOME IMAGEM [--contexto C] [--tamanhos 16,24,32,48]
        Copia uma imagem sua para o tema: SVG vai para scalable/<contexto>; PNG vai para a
        pasta do tamanho dela ou, com --tamanhos, é redimensionado para cada tamanho
        (ImageMagick). Sem --contexto, usa o contexto do nome no tema de referência.

Situações no relatório:
    no tema   - o GTK encontra o ícone no tema (só nas pastas declaradas no index.theme)
    hicolor   - não está no tema; aparece o ícone do próprio aplicativo (tema hicolor)
    faltando  - não está no tema nem no hicolor: o XFCE não mostra ícone

Os nomes que o XFCE pede vêm dos temas de referência (padrão: elementary, o tema de ícones
do XFCE no Arch, e AdwaitaLegacy, com os nomes padrão do freedesktop em cores) e dos ícones
citados nos .desktop dos aplicativos instalados.

Depois de mudar ícones, o script refaz o icon-theme.cache; sem isso o GTK continua usando
a lista antiga. Dependências (Arch Linux): sudo pacman -S --needed gtk3 imagemagick
"""

import argparse
import configparser
import csv
import glob
import html
import os
import re
import shutil
import subprocess
import sys

AQUI = os.path.dirname(os.path.abspath(__file__))
ICONS = os.path.dirname(AQUI)
TEMA = os.path.join(ICONS, "windows-classic")
INDEX = os.path.join(TEMA, "index.theme")
RELATORIO = os.path.join(ICONS, "relatorio-icones.html")

EXTENSOES = (".png", ".svg", ".xpm")
REFERENCIAS = ["elementary", "AdwaitaLegacy"]
PASTAS_ICONES = [os.path.expanduser("~/.local/share/icons"), "/usr/share/icons"]
PASTAS_DESKTOP = ["/usr/share/applications", os.path.expanduser("~/.local/share/applications"),
                  "/etc/xdg/autostart"]
# Context= do index.theme -> nome curto (pasta)
CONTEXTOS = {"actions": "actions", "applications": "apps", "apps": "apps",
             "categories": "categories", "devices": "devices", "emblems": "emblems",
             "mimetypes": "mimetypes", "places": "places", "status": "status",
             "notifications": "notifications", "animations": "animations"}
CONTEXTO_LONGO = {"actions": "Actions", "apps": "Applications", "categories": "Categories",
                  "devices": "Devices", "emblems": "Emblems", "mimetypes": "MimeTypes",
                  "places": "Places", "status": "Status", "notifications": "Notifications",
                  "animations": "Animations"}


# ---------------------------------------------------------------------------
# Leitura de temas
# ---------------------------------------------------------------------------

def ler_index(pasta):
    ini = configparser.ConfigParser(interpolation=None, strict=False)
    ini.optionxform = str
    ini.read(os.path.join(pasta, "index.theme"))
    return ini


def diretorios(ini):
    lista = ini.get("Icon Theme", "Directories", fallback="")
    lista += "," + ini.get("Icon Theme", "ScaledDirectories", fallback="")
    return [d.strip() for d in lista.split(",") if d.strip()]


def tamanho_da_secao(ini, d):
    if not ini.has_section(d):
        return 0
    try:
        return int(ini[d].get("Size", "0"))
    except ValueError:
        return 0


def icones_do_tema(pasta, so_declaradas=True):
    """{nome: [(dir, caminho), ...]} como o GTK vê (só pastas declaradas), sem -symbolic
    a menos que peça. Os diretórios vêm ordenados do maior tamanho para o menor."""
    ini = ler_index(pasta)
    dirs = diretorios(ini) if so_declaradas else sorted(
        os.path.relpath(d, pasta) for d in glob.glob(os.path.join(pasta, "*", "*")) if os.path.isdir(d))
    out = {}
    for d in dirs:
        caminho = os.path.join(pasta, d)
        if not os.path.isdir(caminho):
            continue
        for a in os.listdir(caminho):
            nome, ext = os.path.splitext(a)
            p = os.path.join(caminho, a)
            if ext in EXTENSOES and os.path.exists(p):
                out.setdefault(nome, []).append((d, p))
    return out, ini


def achar_tema(nome):
    for base in PASTAS_ICONES:
        p = os.path.join(base, nome)
        if os.path.isfile(os.path.join(p, "index.theme")):
            return p
    return None


def contexto_de(ini, d):
    return CONTEXTOS.get(ini.get(d, "Context", fallback="").lower(), "outros") if ini.has_section(d) else \
        CONTEXTOS.get(d.split("/")[-1], "outros")


def miniatura(ini, ocorrencias):
    """Caminho da imagem mais perto de 32 px."""
    def chave(oc):
        d = oc[0]
        tam = tamanho_da_secao(ini, d) or 999
        tipo = ini.get(d, "Type", fallback="") if ini.has_section(d) else ""
        return (0 if tipo == "Scalable" else 1) * 0 + abs(tam - 32)
    return min(ocorrencias, key=chave)[1] if ocorrencias else None


def tamanhos_txt(ini, ocorrencias):
    tams = set()
    for d, p in ocorrencias:
        if p.endswith(".svg"):
            tams.add("svg")
        else:
            tams.add(str(tamanho_da_secao(ini, d) or d.split("/")[0]))
    return ", ".join(sorted(tams, key=lambda t: (t == "svg", int(t) if t.isdigit() else 0)))


def nomes_dos_desktop():
    """{ícone: arquivo .desktop} para os ícones citados por nome (não por caminho)."""
    out = {}
    for pasta in PASTAS_DESKTOP:
        for f in sorted(glob.glob(os.path.join(pasta, "*.desktop"))):
            try:
                with open(f, errors="replace") as fh:
                    for linha in fh:
                        if linha.startswith("Icon="):
                            v = linha[5:].strip()
                            if v and "/" not in v:
                                if v.endswith(EXTENSOES):
                                    v = os.path.splitext(v)[0]
                                out.setdefault(v, os.path.basename(f))
                            break
            except OSError:
                pass
    return out


def catalogo(referencias):
    """Situação de cada nome conhecido: lista de dicts."""
    tema, ini = icones_do_tema(TEMA)
    hp = achar_tema("hicolor") or "/usr/share/icons/hicolor"
    hicolor, hini = icones_do_tema(hp)
    refs, usadas = {}, []
    for r in referencias:
        p = achar_tema(r)
        if not p:
            print(f"aviso: tema de referência '{r}' não encontrado", file=sys.stderr)
            continue
        usadas.append(r)
        icones, rini = icones_do_tema(p)
        for nome, oc in icones.items():
            if nome.endswith("-symbolic") or nome in refs:
                continue
            refs[nome] = (contexto_de(rini, oc[0][0]), miniatura(rini, oc), r)
    desktop = nomes_dos_desktop()

    linhas = []
    nomes = {n for n in tema if not n.endswith("-symbolic")} | set(refs) | set(desktop)
    for nome in nomes:
        pedido = [refs[nome][2]] if nome in refs else []
        if nome in desktop:
            pedido.append(desktop[nome])
        if nome in tema:
            oc = tema[nome]
            linhas.append(dict(nome=nome, estado="no tema", ctx=contexto_de(ini, oc[0][0]),
                               prev=miniatura(ini, oc), detalhe=tamanhos_txt(ini, oc),
                               pedido=", ".join(pedido), app=nome in desktop))
            continue
        ctx = "apps" if nome in desktop else (refs[nome][0] if nome in refs else "outros")
        if nome in hicolor:
            linhas.append(dict(nome=nome, estado="hicolor", ctx=ctx,
                               prev=miniatura(hini, hicolor[nome]), detalhe="ícone do aplicativo",
                               pedido=", ".join(pedido), app=nome in desktop))
        else:
            linhas.append(dict(nome=nome, estado="faltando", ctx=ctx,
                               prev=refs[nome][1] if nome in refs else None,
                               detalhe=f"como é em {refs[nome][2]}" if nome in refs else "",
                               pedido=", ".join(pedido), app=nome in desktop))
    return linhas, usadas, len(desktop)


# ---------------------------------------------------------------------------
# Cache
# ---------------------------------------------------------------------------

def refazer_cache():
    if not shutil.which("gtk-update-icon-cache"):
        print("aviso: gtk-update-icon-cache não encontrado (pacote gtk3); cache não refeito")
        return
    r = subprocess.run(["gtk-update-icon-cache", "-f", "-t", TEMA], capture_output=True, text=True)
    print("cache refeito" if r.returncode == 0 else f"falha ao refazer o cache: {r.stderr.strip()}")


# ---------------------------------------------------------------------------
# Comandos
# ---------------------------------------------------------------------------

def cmd_verificar(args):
    ini = ler_index(TEMA)
    decl = diretorios(ini)
    reais = sorted(os.path.relpath(d, TEMA) for d in glob.glob(os.path.join(TEMA, "*", "*"))
                   if os.path.isdir(d))
    nao_decl = [d for d in reais if d not in decl]
    sem_pasta = [d for d in decl if not os.path.isdir(os.path.join(TEMA, d))]
    sem_secao = [d for d in decl + nao_decl if not ini.has_section(d)]
    quebrados = [os.path.relpath(os.path.join(r, a), TEMA) for r, _, fs in os.walk(TEMA) for a in fs
                 if os.path.islink(os.path.join(r, a)) and not os.path.exists(os.path.join(r, a))]
    com_espaco = sorted(os.path.relpath(os.path.join(r, a), TEMA) for r, _, fs in os.walk(TEMA)
                        for a in fs if re.search(r"\s", a))
    nao_icones = sorted(os.path.relpath(os.path.join(r, a), TEMA) for r, _, fs in os.walk(TEMA)
                        for a in fs if r != TEMA and not a.lower().endswith(EXTENSOES))

    problemas = 0
    if nao_decl:
        problemas += 1
        print(f"Pastas fora do Directories= (o GTK não vê estes ícones): {len(nao_decl)}")
        for d in nao_decl:
            print(f"  {d:<26} {len(os.listdir(os.path.join(TEMA, d))):>4} ícones")
    if sem_pasta:
        print(f"Declaradas sem pasta: {', '.join(sem_pasta)}")
    if sem_secao:
        problemas += 1
        print(f"Pastas sem seção [..] no index.theme: {', '.join(sem_secao)}")
    if com_espaco:
        problemas += 1
        print(f"Nomes com espaço (inválidos; o gtk-update-icon-cache não gera o cache): {len(com_espaco)}")
        for q in com_espaco:
            print(f"  {q}")
    if nao_icones:
        print(f"Arquivos que não são ícones (ignorados pelo GTK): {len(nao_icones)}")
        for q in nao_icones[:20]:
            print(f"  {q}")
    if quebrados:
        problemas += 1
        print(f"Links quebrados: {len(quebrados)}")
        for q in quebrados[:20]:
            print(f"  {q}")

    # PNG com tamanho diferente do da pasta (ImageMagick, em lote)
    errados = []
    if shutil.which("magick"):
        for d in decl:
            tam = tamanho_da_secao(ini, d)
            if not tam or ini.get(d, "Type", fallback="Fixed") == "Scalable":
                continue
            pngs = sorted(glob.glob(os.path.join(TEMA, d, "*.png")))
            pngs = [p for p in pngs if os.path.exists(p)]
            for i in range(0, len(pngs), 300):
                r = subprocess.run(["magick", "identify", "-format", "%w %h %i\n", *pngs[i:i + 300]],
                                   capture_output=True, text=True)
                for linha in r.stdout.splitlines():
                    w, h, p = linha.split(" ", 2)
                    if int(w) != tam or int(h) != tam:
                        errados.append((os.path.relpath(p, TEMA), f"{w}x{h}"))
    if errados:
        problemas += 1
        print(f"PNG com tamanho diferente da pasta: {len(errados)}")
        for p, t in errados[:20]:
            print(f"  {p} ({t})")
        if len(errados) > 20:
            print(f"  ... e mais {len(errados) - 20}")

    cache = os.path.join(TEMA, "icon-theme.cache")
    recente = max((os.lstat(os.path.join(r, a)).st_mtime for r, _, fs in os.walk(TEMA) for a in fs
                   if a != "icon-theme.cache"), default=0)
    if os.path.exists(cache) and os.path.getmtime(cache) < recente:
        problemas += 1
        print("O icon-theme.cache é mais antigo que os ícones (o GTK usa a lista antiga).")

    if not problemas:
        print("Nenhum problema encontrado.")
    if args.corrigir and com_espaco:
        for rel in com_espaco:
            origem = os.path.join(TEMA, rel)
            novo = os.path.join(os.path.dirname(origem), re.sub(r"\s+", "-", os.path.basename(origem)))
            if os.path.lexists(novo):
                os.remove(origem)
                print(f"  apagado {rel} (já existe {os.path.basename(novo)})")
            else:
                os.rename(origem, novo)
                print(f"  {rel} -> {os.path.basename(novo)}")
        # Links que apontavam para os nomes antigos passam a apontar para os novos
        for r, _, fs in os.walk(TEMA):
            for a in fs:
                link = os.path.join(r, a)
                if os.path.islink(link) and re.search(r"\s", os.readlink(link)):
                    alvo = os.readlink(link)
                    novo_alvo = os.path.join(os.path.dirname(alvo),
                                             re.sub(r"\s+", "-", os.path.basename(alvo)))
                    os.remove(link)
                    os.symlink(novo_alvo, link)
                    print(f"  link {os.path.relpath(link, TEMA)} -> {novo_alvo}")
    if args.corrigir and (nao_decl or sem_secao):
        corrigir_index(ini, nao_decl, sem_secao)
    if args.corrigir:
        refazer_cache()


def corrigir_index(ini, nao_decl, sem_secao):
    """Acrescenta as pastas ao Directories= e cria as seções que faltam."""
    with open(INDEX) as f:
        texto = f.read()
    if nao_decl:
        texto = re.sub(r"^(Directories=.*)$", lambda m: m.group(1).rstrip(",") + "," + ",".join(nao_decl),
                       texto, count=1, flags=re.M)
    novas = []
    for d in sem_secao:
        tam_txt, ctx = d.split("/")[0], d.split("/")[-1]
        longo = CONTEXTO_LONGO.get(ctx, ctx.capitalize())
        if tam_txt == "scalable":
            novas.append(f"[{d}]\nContext={longo}\nSize=16\nMinSize=8\nMaxSize=512\nType=Scalable\n")
        else:
            tam = tam_txt.split("x")[0]
            novas.append(f"[{d}]\nContext={longo}\nSize={tam}\nType=Fixed\n")
    if novas:
        texto = texto.rstrip("\n") + "\n\n" + "\n".join(novas)
    with open(INDEX, "w") as f:
        f.write(texto)
    print(f"index.theme: {len(nao_decl)} pastas declaradas, {len(novas)} seções criadas")


def cmd_relatorio(args):
    linhas, usadas, n_desktop = catalogo(args.referencia)
    ordem = ["no tema", "hicolor", "faltando"]
    cont = {e: sum(x["estado"] == e for x in linhas) for e in ordem}
    print(f"Nomes conhecidos: {len(linhas)} (referências: {', '.join(usadas) or 'nenhuma'}; "
          f"ícones citados em .desktop: {n_desktop})")
    for e in ordem:
        print(f"  {e:<9} {cont[e]:>5}")
    print("\nPor contexto (no tema / hicolor / faltando):")
    ctxs = sorted({x["ctx"] for x in linhas}, key=lambda c: (c == "outros", c))
    for c in ctxs:
        n = [sum(x["ctx"] == c and x["estado"] == e for x in linhas) for e in ordem]
        print(f"  {c:<14} " + " / ".join(f"{v:>4}" for v in n))
    faltam_apps = sum(x["estado"] != "no tema" and x["app"] for x in linhas)
    print(f"\nÍcones de aplicativos instalados fora do tema: {faltam_apps}")
    gerar_html(linhas, ordem, cont, usadas, ctxs)
    print(f"Relatório com miniaturas: {RELATORIO}")


def cmd_faltando(args):
    linhas, _, _ = catalogo(args.referencia)
    sel = sorted((x for x in linhas if x["estado"] == "faltando"),
                 key=lambda x: (not x["app"], x["ctx"], x["nome"]))
    if args.csv:
        with open(args.csv, "w", newline="") as f:
            w = csv.writer(f)
            w.writerow(["nome", "contexto", "pedido_por", "referencia"])
            for x in sel:
                w.writerow([x["nome"], x["ctx"], x["pedido"], x["prev"] or ""])
        print(f"{len(sel)} nomes em {args.csv}")
        return
    for x in sel:
        print(f"{x['ctx']:<14} {x['nome']:<45} {x['pedido']}")
    print(f"\n{len(sel)} nomes faltando")


def cmd_procurar(args):
    tema, ini = icones_do_tema(TEMA)
    achados = sorted(n for n in tema if args.texto.lower() in n.lower())
    for n in achados:
        print(f"{n:<50} {contexto_de(ini, tema[n][0][0]):<14} {tamanhos_txt(ini, tema[n])}")
    print(f"\n{len(achados)} ícones")


def cmd_apelido(args):
    tema, ini = icones_do_tema(TEMA)
    if args.existente not in tema:
        sys.exit(f"'{args.existente}' não está no tema (veja 'procurar')")
    criados = 0
    for d, p in tema[args.existente]:
        ext = os.path.splitext(p)[1]
        link = os.path.join(TEMA, d, args.novo + ext)
        if os.path.lexists(link):
            print(f"  já existe: {os.path.relpath(link, TEMA)}")
            continue
        alvo = os.path.basename(p) if not os.path.islink(p) else os.readlink(p)
        if os.path.islink(p) and os.path.isabs(alvo):
            alvo = os.path.relpath(alvo, os.path.dirname(link))
        os.symlink(alvo, link)
        print(f"  {os.path.relpath(link, TEMA)} -> {alvo}")
        criados += 1
    print(f"{criados} links criados")
    if criados:
        refazer_cache()


def cmd_adicionar(args):
    if not os.path.isfile(args.imagem):
        sys.exit(f"arquivo não encontrado: {args.imagem}")
    ext = os.path.splitext(args.imagem)[1].lower()
    if ext not in (".png", ".svg"):
        sys.exit("use uma imagem .png ou .svg")
    ctx = args.contexto
    if not ctx:
        linhas, _, _ = catalogo(REFERENCIAS)
        ctx = next((x["ctx"] for x in linhas if x["nome"] == args.nome), None)
        if not ctx or ctx == "outros":
            sys.exit("não sei o contexto deste nome; use --contexto (actions, apps, categories, "
                     "devices, emblems, mimetypes, places, status, notifications)")
    ini = ler_index(TEMA)
    destinos = []
    if ext == ".svg":
        destinos.append((f"scalable/{ctx}", None))
    elif args.tamanhos:
        if not shutil.which("magick"):
            sys.exit("ImageMagick não encontrado (sudo pacman -S --needed imagemagick)")
        for t in args.tamanhos.split(","):
            destinos.append((f"{t}x{t}/{ctx}", int(t)))
    else:
        r = subprocess.run(["magick", "identify", "-format", "%w", args.imagem + "[0]"],
                           capture_output=True, text=True, check=True)
        t = int(r.stdout)
        destinos.append((f"{t}x{t}/{ctx}", None))
    novas = []
    for d, tam in destinos:
        pasta = os.path.join(TEMA, d)
        os.makedirs(pasta, exist_ok=True)
        dest = os.path.join(pasta, args.nome + ext)
        if tam:
            subprocess.run(["magick", args.imagem, "-background", "none", "-resize", f"{tam}x{tam}",
                            "-gravity", "center", "-extent", f"{tam}x{tam}", "PNG32:" + dest], check=True)
        else:
            shutil.copyfile(args.imagem, dest)
        print(f"  {os.path.relpath(dest, TEMA)}")
        if d not in diretorios(ini):
            novas.append(d)
    if novas:
        corrigir_index(ini, novas, [d for d in novas if not ini.has_section(d)])
    refazer_cache()


# ---------------------------------------------------------------------------
# HTML
# ---------------------------------------------------------------------------

def gerar_html(linhas, ordem, cont, refs, ctxs):
    cores = {"no tema": "#008000", "hicolor": "#806000", "faltando": "#a00000"}
    p = ["<!doctype html><meta charset='utf-8'><title>Ícones windows-classic</title><style>"
         "body{font:13px 'Noto Sans',sans-serif;background:#d4d0c8;margin:16px}"
         "h1{font-size:18px}h2{font-size:15px;margin-top:24px}"
         "table{border-collapse:collapse;background:#fff;border:1px solid #808080}"
         "td,th{padding:3px 8px;border-bottom:1px solid #e8e8e8;text-align:left;vertical-align:middle}"
         "th{background:#d4d0c8}img{width:32px;height:32px;object-fit:contain}"
         "tr[data-e=faltando] img{opacity:.55}code{font-size:12px}.e{font-weight:bold}"
         ".app{background:#ffffe1}</style>",
         "<h1>Tema de ícones windows-classic</h1>",
         "<p>Referências: " + html.escape(", ".join(refs) or "nenhuma") + " e os .desktop instalados. "
         + " · ".join(f"<span class='e' style='color:{cores[e]}'>{e}</span>: {cont[e]}" for e in ordem)
         + ". Linhas amarelas: ícones de aplicativos instalados. Para os que faltam, a miniatura "
         "(clara) é a do tema de referência.</p>",
         "<p id='f'>Mostrar: " + " ".join(f"<label><input type='checkbox' checked data-e='{e}'> {e}</label>"
                                         for e in ordem)
         + " &nbsp; <label>Procurar: <input id='q' size='24'></label></p>"]
    for c in ctxs:
        sel = sorted((x for x in linhas if x["ctx"] == c),
                     key=lambda x: (ordem.index(x["estado"]), not x["app"], x["nome"]))
        p.append(f"<h2>{c} ({len(sel)})</h2><table><tr><th></th><th>Nome</th><th>Situação</th>"
                 "<th>Tamanhos / origem</th><th>Pedido por</th></tr>")
        for x in sel:
            img = f"<img src='file://{html.escape(x['prev'])}'>" if x["prev"] else ""
            cls = " class='app'" if x["app"] and x["estado"] != "no tema" else ""
            p.append(f"<tr data-e='{x['estado']}' data-n='{html.escape(x['nome'])}'{cls}><td>{img}</td>"
                     f"<td><code>{html.escape(x['nome'])}</code></td>"
                     f"<td class='e' style='color:{cores[x['estado']]}'>{x['estado']}</td>"
                     f"<td>{html.escape(x['detalhe'])}</td><td>{html.escape(x['pedido'])}</td></tr>")
        p.append("</table>")
    p.append("<script>function f(){const on=[...document.querySelectorAll('#f input[data-e]')]"
             ".filter(c=>c.checked).map(c=>c.dataset.e),q=document.getElementById('q').value.toLowerCase();"
             "document.querySelectorAll('tr[data-e]').forEach(r=>r.style.display="
             "on.includes(r.dataset.e)&&r.dataset.n.includes(q)?'':'none')}"
             "document.querySelectorAll('#f input').forEach(i=>i.oninput=f)</script>")
    with open(RELATORIO, "w") as fh:
        fh.write("\n".join(p))


# ---------------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser(description="Mapeador do tema de ícones windows-classic.")
    sub = ap.add_subparsers(dest="cmd", required=True)
    v = sub.add_parser("verificar", help="confere a estrutura do tema")
    v.add_argument("--corrigir", action="store_true", help="declara as pastas que faltam e refaz o cache")
    v.set_defaults(f=cmd_verificar)
    for nome, func, ajuda in (("relatorio", cmd_relatorio, "resumo e relatório HTML"),
                              ("faltando", cmd_faltando, "lista os nomes que faltam")):
        s = sub.add_parser(nome, help=ajuda)
        s.add_argument("--referencia", nargs="+", default=REFERENCIAS, metavar="TEMA")
        if nome == "faltando":
            s.add_argument("--csv", metavar="ARQUIVO", help="grava a lista em CSV")
        s.set_defaults(f=func)
    s = sub.add_parser("procurar", help="procura ícones do tema pelo nome")
    s.add_argument("texto")
    s.set_defaults(f=cmd_procurar)
    s = sub.add_parser("apelido", help="cria um nome novo apontando para um ícone existente")
    s.add_argument("novo")
    s.add_argument("existente")
    s.set_defaults(f=cmd_apelido)
    s = sub.add_parser("adicionar", help="copia uma imagem sua para o tema")
    s.add_argument("nome")
    s.add_argument("imagem")
    s.add_argument("--contexto")
    s.add_argument("--tamanhos", help="ex.: 16,24,32,48 (redimensiona um PNG)")
    s.set_defaults(f=cmd_adicionar)
    args = ap.parse_args()
    args.f(args)


if __name__ == "__main__":
    main()
