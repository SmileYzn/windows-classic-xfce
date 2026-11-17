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
  - todos os ícones do tema, inclusive os nomes extras (gtk-*, gnome-*, etc.);
  - de onde vem cada ícone que falta (Adwaita, hicolor ou nenhum = fica em branco);
  - a galeria de ícones extraídos da I386 (Icons/src/extrair-i386.py), se existir.

Na página dá para montar uma lista dos ícones que serão adicionados à mão
(origem: um ícone da I386 ou um arquivo seu) e exportá-la como .list.

Uso:
    python3 Icons/src/mapa.py              # gera Icons/mapa.html
Depois abra Icons/mapa.html no navegador. Rode de novo sempre que o tema mudar.
"""

import configparser
import glob
import json
import os
import shutil
import tempfile
import datetime

import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk  # noqa: E402

AQUI = os.path.dirname(os.path.abspath(__file__))
ICONS = os.path.dirname(AQUI)                          # pasta Icons/
TEMA = "windows-classic-icons"
RAIZ_TEMA = os.path.join(ICONS, TEMA)
I386 = os.path.join(ICONS, "build", "i386")
SAIDA = os.path.join(ICONS, "mapa.html")
TAMANHOS = [16, 22, 24, 32, 48, "scalable"]

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
    """{nome: contexto} dos ícones coloridos (sem -symbolic) instalados no hicolor."""
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
        out[n] = os.path.relpath(info.get_filename(), busca).split(os.sep)[0]
    return out


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
    faltam = ({n for _, n in padrao if n not in tema} | {n for n in apps if n not in tema}
              | {n for _, n in hicolor if n not in tema})
    i386 = []
    indice = os.path.join(I386, "indice.json")
    if os.path.exists(indice):
        with open(indice, encoding="utf-8") as f:
            i386 = json.load(f)
    dados = {
        "tema": tema, "padrao": padrao, "apps": apps, "hicolor": hicolor, "heranca": heranca(sorted(faltam)),
        "i386": i386, "tamanhos": TAMANHOS, "nomeTema": TEMA, "listaProjeto": ler_lista(),
        "gerado": datetime.datetime.now().strftime("%d/%m/%Y %H:%M"),
    }
    with open(os.path.join(AQUI, "mapa.template.html"), encoding="utf-8") as f:
        html = f.read()
    html = html.replace("/*__DADOS__*/null", json.dumps(dados, ensure_ascii=False, separators=(",", ":")))
    with open(SAIDA, "w", encoding="utf-8") as f:
        f.write(html)
    n_i386 = sum(len(a["grupos"]) for a in i386)
    print("OK: %s (%d ícones no tema, %d nomes padrão, %d ícones de apps, %d do hicolor, %d da I386)"
          % (SAIDA, len(tema), len(padrao), len(apps), len(hicolor), n_i386))
    if not i386:
        print("Dica: rode Icons/src/extrair-i386.py /caminho/para/I386 para ver a galeria da I386.")


if __name__ == "__main__":
    main()
