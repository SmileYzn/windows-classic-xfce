#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Gera o Icons/mapa.html: um mapa do tema de ícones windows-classic-icons.

O mapa mostra:
  - os nomes da Icon Naming Specification do freedesktop.org e os do tema AdwaitaLegacy
    (ícones coloridos que o GTK e o XFCE ainda pedem), e quais tamanhos o tema tem;
  - os ícones pedidos pelos aplicativos instalados (linha Icon= dos arquivos .desktop);
  - os ícones que os aplicativos e os plugins do painel instalam no hicolor
    (ex.: org.xfce.panel.showdesktop);
  - os nomes coloridos do tema elementary (/usr/share/icons/elementary), que o XFCE e
    vários aplicativos pedem;
  - para cada nome que falta, uma miniatura de referência apontando para o arquivo
    original em /usr/share/icons (nada é copiado: é só para ver o que o nome representa);
  - todos os ícones do tema, inclusive os nomes extras (gtk-*, gnome-*, etc.);
  - de onde vem cada ícone que falta (Adwaita, hicolor ou nenhum = fica em branco);
  - a galeria XP: os ícones de Icons/build/xp-icons/<N>x<N>/<nome>.png, em todos os
    tamanhos das subpastas (16, 22, 24, 32, 48, 64, 128, 1024...);
  - a galeria de ícones extraídos da I386 (Icons/src/extrair-i386.py), se existir.

Na página dá para montar uma lista dos ícones que serão adicionados à mão
(origem: xp:<nome>, i386:<arquivo>#<grupo> ou um arquivo seu) e exportá-la como .list.

Uso:
    python3 Icons/src/mapa.py              # gera Icons/mapa.html
Depois abra Icons/mapa.html no navegador. Rode de novo sempre que o tema mudar.
"""

import configparser
import glob
import json
import os
import shutil
import struct
import tempfile
import urllib.parse
import datetime

import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk  # noqa: E402

AQUI = os.path.dirname(os.path.abspath(__file__))
ICONS = os.path.dirname(AQUI)                          # pasta Icons/
TEMA = "windows-classic-icons"
RAIZ_TEMA = os.path.join(ICONS, TEMA)
I386 = os.path.join(ICONS, "build", "i386")
XP_ICONS = os.path.join(ICONS, "build", "xp-icons")
SAIDA = os.path.join(ICONS, "mapa.html")
TAMANHOS = [16, 22, 24, 32, 36, 48, 64, 96, 128]   # mesmos de gerar-index.py

# Icon Naming Specification 0.8.90 (nomes por contexto)
ESPEC = {
    "actions": """address-book-new application-exit appointment-new call-start call-stop contact-new
        document-new document-open document-open-recent document-page-setup document-print
        document-print-preview document-properties document-revert document-save document-save-as
        document-send edit-clear edit-copy edit-cut edit-delete edit-find edit-find-replace edit-paste
        edit-redo edit-select-all edit-undo folder-new format-indent-less format-indent-more
        format-justify-center format-justify-fill format-justify-left format-justify-right
        format-text-direction-ltr format-text-direction-rtl format-text-bold format-text-italic
        format-text-underline format-text-strikethrough go-bottom go-down go-first go-home go-jump
        go-last go-next go-previous go-top go-up help-about help-contents help-faq insert-image
        insert-link insert-object insert-text list-add list-remove mail-forward mail-mark-important
        mail-mark-junk mail-mark-notjunk mail-mark-read mail-mark-unread mail-message-new
        mail-reply-all mail-reply-sender mail-send mail-send-receive media-eject media-playback-pause
        media-playback-start media-playback-stop media-record media-seek-backward media-seek-forward
        media-skip-backward media-skip-forward object-flip-horizontal object-flip-vertical
        object-rotate-left object-rotate-right process-stop system-lock-screen system-log-out
        system-run system-search system-reboot system-shutdown tools-check-spelling view-fullscreen
        view-refresh view-restore view-sort-ascending view-sort-descending window-close window-new
        zoom-fit-best zoom-in zoom-original zoom-out""",
    "animations": "process-working",
    "apps": """accessories-calculator accessories-character-map accessories-dictionary
        accessories-text-editor help-browser multimedia-volume-control
        preferences-desktop-accessibility preferences-desktop-font preferences-desktop-keyboard
        preferences-desktop-locale preferences-desktop-multimedia preferences-desktop-screensaver
        preferences-desktop-theme preferences-desktop-wallpaper system-file-manager
        system-software-install system-software-update utilities-system-monitor utilities-terminal""",
    "categories": """applications-accessories applications-development applications-engineering
        applications-games applications-graphics applications-internet applications-multimedia
        applications-office applications-other applications-science applications-system
        applications-utilities preferences-desktop preferences-desktop-peripherals
        preferences-desktop-personal preferences-other preferences-system preferences-system-network
        system-help""",
    "devices": """audio-card audio-input-microphone battery camera-photo camera-video camera-web
        computer drive-harddisk drive-optical drive-removable-media input-gaming input-keyboard
        input-mouse input-tablet media-flash media-floppy media-optical media-tape modem
        multimedia-player network-wired network-wireless pda phone printer scanner video-display""",
    "emblems": """emblem-default emblem-documents emblem-downloads emblem-favorite emblem-important
        emblem-mail emblem-photos emblem-readonly emblem-shared emblem-symbolic-link
        emblem-synchronized emblem-system emblem-unreadable""",
    "mimetypes": """application-x-executable audio-x-generic font-x-generic image-x-generic
        package-x-generic text-html text-x-generic text-x-generic-template text-x-script
        video-x-generic x-office-address-book x-office-calendar x-office-document
        x-office-presentation x-office-spreadsheet""",
    "places": """folder folder-remote network-server network-workgroup start-here user-bookmarks
        user-desktop user-home user-trash""",
    "status": """appointment-missed appointment-soon audio-volume-high audio-volume-low
        audio-volume-medium audio-volume-muted battery-caution battery-low dialog-error
        dialog-information dialog-password dialog-question dialog-warning folder-drag-accept
        folder-open folder-visiting image-loading image-missing mail-attachment mail-unread
        mail-read mail-replied mail-signed mail-signed-verified media-playlist-repeat
        media-playlist-shuffle network-error network-idle network-offline network-receive
        network-transmit network-transmit-receive printer-error printer-printing security-high
        security-medium security-low software-update-available software-update-urgent sync-error
        sync-synchronizing task-due task-past-due user-available user-away user-idle user-offline
        user-trash-full weather-clear weather-clear-night weather-few-clouds
        weather-few-clouds-night weather-fog weather-overcast weather-severe-alert weather-showers
        weather-showers-scattered weather-snow weather-storm""",
}


ADWAITA_LEGACY = "/usr/share/icons/AdwaitaLegacy"


def nomes_adwaita_legacy(tema):
    """[[contexto, nome]] dos ícones coloridos (sem -symbolic) do AdwaitaLegacy. Os que lá
    estão na pasta "legacy" usam o contexto do nome no tema, quando ele já existe."""
    cp = configparser.ConfigParser(interpolation=None, strict=False)
    cp.optionxform = str
    if not cp.read(os.path.join(ADWAITA_LEGACY, "index.theme"), encoding="utf-8"):
        return []
    out = {}
    for d in cp["Icon Theme"]["Directories"].split(","):
        pasta = os.path.join(ADWAITA_LEGACY, d)
        if not os.path.isdir(pasta):
            continue
        ctx = d.split("/")[-1]
        for f in os.listdir(pasta):
            nome, ext = os.path.splitext(f)
            if ext not in (".png", ".svg") or nome.endswith("-symbolic") or nome.startswith("."):
                continue
            if ctx == "legacy" and nome in tema:
                out.setdefault(nome, tema[nome]["c"])
            else:
                out.setdefault(nome, ctx)
    return [[c, n] for n, c in sorted(out.items())]


HICOLOR = "/usr/share/icons/hicolor"
# pastas do hicolor fora da especificação -> contexto do tema
CTX_HICOLOR = {"media": "actions", "navigation": "actions", "stock": "actions"}


def nomes_hicolor():
    """{nome: contexto} dos ícones coloridos (sem -symbolic) instalados no hicolor.
    Guarda também em REFS um arquivo de cada nome, para a miniatura de referência."""
    cp = configparser.ConfigParser(interpolation=None, strict=False)
    cp.optionxform = str
    if not cp.read(os.path.join(HICOLOR, "index.theme"), encoding="utf-8"):
        return {}
    out = {}
    for d in cp["Icon Theme"]["Directories"].split(","):
        pasta = os.path.join(HICOLOR, d)
        if not os.path.isdir(pasta):
            continue
        ctx = d.split("/")[-1]
        for f in os.listdir(pasta):
            nome, ext = os.path.splitext(f)
            if ext in (".png", ".svg") and not nome.endswith("-symbolic") and not nome.startswith("."):
                out.setdefault(nome, CTX_HICOLOR.get(ctx, ctx))
                guardar_ref(nome, os.path.join(pasta, f), d.split("/")[0])
    return out


ELEMENTARY = "/usr/share/icons/elementary"
# pastas do elementary (contexto/tamanho) -> contexto do tema
CTX_ELEMENTARY = {"mimes": "mimetypes"}

# {nome: (prioridade, arquivo)} da miniatura de referência; prefere 48 px, depois 32, SVG...
REFS = {}


def guardar_ref(nome, caminho, tamanho):
    """Guarda o arquivo de referência de um nome, preferindo o tamanho mais próximo de 48."""
    if caminho.endswith(".xpm"):
        return
    num = "".join(c for c in tamanho.split("x")[0] if c.isdigit())
    prio = abs(int(num) - 48) if num else 40          # "scalable" e afins: no meio
    if nome not in REFS or prio < REFS[nome][0]:
        REFS[nome] = (prio, caminho)


def nomes_elementary():
    """{nome: contexto} dos ícones coloridos do elementary (sem -symbolic e sem as
    variantes @2x/@3x). O elementary organiza as pastas como <contexto>/<tamanho>."""
    out = {}
    if not os.path.isdir(ELEMENTARY):
        return out
    for ctx in sorted(os.listdir(ELEMENTARY)):
        base = os.path.join(ELEMENTARY, ctx)
        if "@" in ctx or not os.path.isdir(base) or ctx.startswith("cursor"):
            continue
        for tam in sorted(os.listdir(base)):
            pasta = os.path.join(base, tam)
            if tam == "symbolic" or not os.path.isdir(pasta):
                continue
            for f in os.listdir(pasta):
                nome, ext = os.path.splitext(f)
                if ext in (".png", ".svg") and not nome.endswith("-symbolic") and not nome.startswith("."):
                    out.setdefault(nome, CTX_ELEMENTARY.get(ctx, ctx))
                    guardar_ref(nome, os.path.join(pasta, f), tam)
    return out


def ler_tema():
    """{nome: {"c": contexto, "s": {tamanho: caminho}, "a": alvo do link}}"""
    cp = configparser.ConfigParser(interpolation=None, strict=False)
    cp.optionxform = str
    cp.read(os.path.join(RAIZ_TEMA, "index.theme"), encoding="utf-8")
    tema = {}
    for d in cp["Icon Theme"]["Directories"].split(","):
        # pastas escaláveis (SVG) entram na coluna "scalable"
        tam = "scalable" if cp[d].get("Type") == "Scalable" else int(cp[d]["Size"])
        ctx = d.split("/")[1]
        pasta = os.path.join(RAIZ_TEMA, d)
        for f in sorted(os.listdir(pasta)):
            nome, ext = os.path.splitext(f)
            if ext not in (".png", ".svg"):
                continue
            item = tema.setdefault(nome, {"c": ctx, "s": {}})
            item["s"][tam] = "%s/%s/%s" % (TEMA, d, f)
            p = os.path.join(pasta, f)
            if os.path.islink(p):
                item["a"] = os.path.splitext(os.path.basename(os.path.realpath(p)))[0]
    return tema


def ler_apps():
    """Ícones pedidos pelos .desktop instalados: {ícone: [nomes dos aplicativos]}"""
    apps = {}
    pastas = ["/usr/share/applications", os.path.expanduser("~/.local/share/applications")]
    for pasta in pastas:
        for arq in sorted(glob.glob(os.path.join(pasta, "**", "*.desktop"), recursive=True)):
            cp = configparser.ConfigParser(interpolation=None, strict=False)
            cp.optionxform = str
            try:
                cp.read(arq, encoding="utf-8")
                ent = cp["Desktop Entry"]
            except (configparser.Error, KeyError, UnicodeDecodeError):
                continue
            icone = ent.get("Icon", "").strip()
            if not icone or "/" in icone or ent.get("NoDisplay", "").lower() == "true":
                continue
            nome = ent.get("Name[pt_BR]") or ent.get("Name") or os.path.basename(arq)
            apps.setdefault(icone, []).append(nome)
    return apps


def heranca(nomes):
    """Para cada nome ausente do tema, de qual tema herdado ele vem (ou None)."""
    # O GTK mescla pastas de tema com o mesmo nome em todo o caminho de busca. Para que
    # uma cópia instalada (ex.: /usr/share/icons/windows-classic-icons) não se misture
    # com a do projeto, monta uma pasta temporária com links para os temas do sistema,
    # menos os que têm o nome deste tema.
    busca = tempfile.mkdtemp(prefix="mapa-icones-")
    os.symlink(RAIZ_TEMA, os.path.join(busca, TEMA))
    for base in (os.path.expanduser("~/.local/share/icons"), "/usr/share/icons"):  # ordem do GTK
        if not os.path.isdir(base):
            continue
        for t in os.listdir(base):
            if t != TEMA and not os.path.lexists(os.path.join(busca, t)):
                os.symlink(os.path.join(base, t), os.path.join(busca, t))
    th = Gtk.IconTheme()
    th.set_search_path([busca])
    th.set_custom_theme(TEMA)
    out = {}
    try:
        _procurar(th, busca, nomes, out)
    finally:
        shutil.rmtree(busca)
    return out


def _procurar(th, busca, nomes, out):
    for n in nomes:
        info = th.lookup_icon(n, 48, 0)
        if not info or not info.get_filename():
            out[n] = None
            continue
        rel = os.path.relpath(info.get_filename(), busca)
        out[n] = rel.split(os.sep)[0]
        if out[n] != TEMA:
            # a miniatura de referência é o arquivo que o GTK mostra hoje para esse nome
            # (fora da pasta temporária); hicolor/elementary ficam para quem não tem herança
            REFS[n] = (-1, os.path.realpath(info.get_filename()))
    return out


ADWAITA_SIMB = "/usr/share/icons/Adwaita/symbolic"
# O tema só tem as pastas de contexto padrão; as pastas "ui", "legacy" e "emotes" do Adwaita
# simbólico entram no contexto mais próximo (o GTK procura o nome em qualquer pasta do tema).
CTX_SIMB = {"ui": "actions", "legacy": "apps", "emotes": "status"}


def nomes_simbolicos():
    """[[contexto, nome]] dos ícones simbólicos (-symbolic) do Adwaita. São os pretos que
    aparecem na área de notificação, nas barras de ferramentas e nos menus."""
    out = {}
    if not os.path.isdir(ADWAITA_SIMB):
        return []
    for ctx in sorted(os.listdir(ADWAITA_SIMB)):
        pasta = os.path.join(ADWAITA_SIMB, ctx)
        if not os.path.isdir(pasta):
            continue
        for f in sorted(os.listdir(pasta)):
            nome, ext = os.path.splitext(f)
            if ext != ".svg" or not nome.endswith("-symbolic"):
                continue
            c = CTX_SIMB.get(ctx, ctx)
            if ctx == "legacy" and nome.startswith("emblem-"):
                c = "emblems"
            out.setdefault(nome, c)
    return [[c, n] for n, c in sorted(out.items())]


def uso_simbolicos(nomes):
    """{nome: [programas]} dos simbólicos que aparecem (como texto) nos programas e bibliotecas
    do XFCE e do GTK instalados: é o que eles pedem ao tema de ícones."""
    alvos = set()
    for pad in ("/usr/bin/thunar", "/usr/bin/mousepad", "/usr/bin/ristretto", "/usr/bin/xfce4-*",
                "/usr/bin/xfdesktop", "/usr/bin/xfwm4", "/usr/bin/xfsettingsd", "/usr/bin/engrampa",
                "/usr/bin/catfish", "/usr/bin/parole", "/usr/lib/xfce4/**/*.so", "/usr/lib/libxfce*",
                "/usr/lib/thunarx-3/*.so", "/usr/lib/libthunar*", "/usr/lib/libgtk-3.so.0",
                "/usr/lib/libwnck*"):
        for f in glob.glob(pad, recursive=True):
            if os.path.isfile(f):
                alvos.add(os.path.realpath(f))
    uso = {}
    for f in sorted(alvos):
        try:
            with open(f, "rb") as fh:
                dados = fh.read()
        except OSError:
            continue
        prog = os.path.basename(f)
        prog = prog[:-3] if prog.endswith(".so") else prog
        prog = prog[3:] if prog.startswith("lib") else prog
        prog = prog.split(".so")[0]
        for n in nomes:
            if n.encode() in dados:
                uso.setdefault(n, [])
                if prog not in uso[n]:
                    uso[n].append(prog)
    return uso


def ler_xp_icons():
    """[{nome, tamanhos}] da galeria XP: cada subpasta NxN de Icons/build/xp-icons
    é um tamanho; o nome do ícone é o nome do arquivo sem .png (pode ter espaços)."""
    if not os.path.isdir(XP_ICONS):
        return []
    tams = {}
    fora = set()        # nomes com algum PNG que não é NxN (ex.: "Icon Pack", a imagem de divulgação)
    for d in os.listdir(XP_ICONS):
        w, _, h = d.partition("x")
        if not (w.isdigit() and w == h and os.path.isdir(os.path.join(XP_ICONS, d))):
            continue
        for f in os.listdir(os.path.join(XP_ICONS, d)):
            nome, ext = os.path.splitext(f)
            if ext.lower() != ".png" or nome.startswith("."):
                continue
            dim = dimensoes_png(os.path.join(XP_ICONS, d, f))
            if not dim or dim[0] != dim[1]:
                fora.add(nome)              # não é ícone (imagem não quadrada)
                continue
            tams.setdefault(nome, set())
            if dim[0] == int(w):            # quadrado de outro tamanho (ex.: 1500 px na pasta
                tams[nome].add(int(w))      # 1024x1024) só não conta para esta pasta
    return [{"nome": n, "tamanhos": sorted(s)}
            for n, s in sorted(tams.items(), key=lambda kv: kv[0].lower()) if n not in fora]


def dimensoes_png(caminho):
    """(largura, altura) lidas do cabeçalho IHDR, sem abrir a imagem inteira."""
    with open(caminho, "rb") as f:
        cab = f.read(24)
    if cab[:8] != b"\x89PNG\r\n\x1a\n":
        return None
    return struct.unpack(">II", cab[16:24])


LISTA = os.path.join(ICONS, TEMA + ".list")


def ler_lista():
    """Itens do Icons/windows-classic-icons.list, para a página começar com a lista inteira."""
    itens = []
    if not os.path.exists(LISTA):
        return itens
    with open(LISTA, encoding="utf-8") as f:
        for linha in f:
            linha = linha.rstrip("\n")
            if not linha.strip() or linha.startswith("#"):
                continue
            partes = (linha.split("\t") + ["", "", ""])[:4]
            if "/" not in partes[0]:
                continue
            ctx, nome = partes[0].rsplit("/", 1)
            tams = [t if t == "scalable" else int(t) for t in partes[2].split(",") if t.strip()]
            itens.append({"nome": nome, "ctx": ctx, "origem": partes[1], "tamanhos": tams, "obs": partes[3]})
    return itens


def main():
    tema = ler_tema()
    apps = ler_apps()
    padrao = [[c, n] for c, nomes in ESPEC.items() for n in nomes.split()]
    na_espec = {n for _, n in padrao}
    padrao += [[c, n] for c, n in nomes_adwaita_legacy(tema) if n not in na_espec]
    ja = {n for _, n in padrao}
    hicolor = [[c, n] for n, c in sorted(nomes_hicolor().items()) if n not in ja and n not in apps]
    ja |= {n for _, n in hicolor}
    elementary = [[c, n] for n, c in sorted(nomes_elementary().items())
                  if n not in ja and n not in apps and n not in tema]
    simbolicos = nomes_simbolicos()
    uso_simb = uso_simbolicos([n for _, n in simbolicos])
    faltam = ({n for _, n in simbolicos if n not in tema} | {n for _, n in padrao if n not in tema} | {n for n in apps if n not in tema}
              | {n for _, n in hicolor if n not in tema} | {n for _, n in elementary})
    i386 = []
    indice = os.path.join(I386, "indice.json")
    if os.path.exists(indice):
        with open(indice, encoding="utf-8") as f:
            i386 = json.load(f)
    xp = ler_xp_icons()
    dados = {
        "tema": tema, "padrao": padrao, "apps": apps, "hicolor": hicolor, "elementary": elementary,
        "simbolicos": simbolicos, "usoSimb": uso_simb,
        "heranca": heranca(sorted(faltam)),
        "i386": i386, "xp": xp, "tamanhos": TAMANHOS, "nomeTema": TEMA, "listaProjeto": ler_lista(),
        "gerado": datetime.datetime.now().strftime("%d/%m/%Y %H:%M"),
    }
    # miniaturas de referência só para os nomes que faltam no tema
    dados["refs"] = {n: "file://" + urllib.parse.quote(REFS[n][1]) for n in sorted(faltam) if n in REFS}
    with open(os.path.join(AQUI, "mapa.template.html"), encoding="utf-8") as f:
        html = f.read()
    html = html.replace("/*__DADOS__*/null", json.dumps(dados, ensure_ascii=False, separators=(",", ":")))
    with open(SAIDA, "w", encoding="utf-8") as f:
        f.write(html)
    n_i386 = sum(len(a["grupos"]) for a in i386)
    print("OK: %s (%d ícones no tema, %d nomes padrão, %d ícones de apps, %d do hicolor, %d do elementary, "
          "%d simbólicos (%d usados), %d da galeria XP, %d da I386)"
          % (SAIDA, len(tema), len(padrao), len(apps), len(hicolor), len(elementary), len(simbolicos),
             len(uso_simb), len(xp), n_i386))
    if not i386:
        print("Dica: rode Icons/src/extrair-i386.py /caminho/para/I386 para ver a galeria da I386.")


if __name__ == "__main__":
    main()
