#!/usr/bin/env python3
"""Instalador do tema Windows Classic (Windows XP clássico) para XFCE.

Sem argumentos abre o assistente. No terminal:

    python3 Setup/windows-classic-installer.py --list
    python3 Setup/windows-classic-installer.py --install all
    python3 Setup/windows-classic-installer.py --install theme,cursors --system
    python3 Setup/windows-classic-installer.py --install all --with-panel
    python3 Setup/windows-classic-installer.py --uninstall all

Modos:
  - "Somente para mim" (padrão): copia para a pasta pessoal (~/.local/share), sem senha.
  - "Todos os usuários" (--system): copia para /usr/share. Só a cópia roda como root, com o
    próprio script chamado de novo pelo pkexec (--root); a janela nunca roda como root.

"Aplicar" ativa cada parte no XFCE (xfconf-query). Ao remover, essas configurações voltam ao
padrão do XFCE. O componente "panel" carrega o perfil Panel/windows-classic.tar.bz2
(xfce4-panel-profiles) no lugar do painel atual. Nada é guardado como backup.

Dependências (Arch Linux):
    sudo pacman -S --needed python-gobject gtk3 polkit
"""

import argparse
import atexit
import base64
import os
import shutil
import signal
import subprocess
import sys
import tempfile
import threading
from pathlib import Path

SRC = Path(__file__).resolve().parent.parent   # raiz do projeto (o script fica em Setup/)
HOME = Path.home()
MARK = ".windows-classic-xfce"       # marca as pastas instaladas por este instalador
PANEL_PROFILE = SRC / "Panel/windows-classic.tar.bz2"
NAME = "windows-classic"
# Ambiente original para os comandos chamados: a janela muda GTK_THEME e XDG_DATA_DIRS só
# para si mesma (veja use_project_theme).
CHILD_ENV = dict(os.environ)
# xfconf-query lê e escreve números conforme o idioma (0,9 em pt_BR); em C é sempre 0.9.
XFCONF_ENV = dict(CHILD_ENV, LC_ALL="C")

# Componentes na ordem de instalação. "files": (origem no projeto, destino).
COMPONENTS = {
    "cursors": {
        "label": "Cursores do Windows XP",
        "files": {
            "system": [("Cursors/windows-classic-cursors", "/usr/share/icons/windows-classic-cursors")],
            "user": [("Cursors/windows-classic-cursors", "~/.local/share/icons/windows-classic-cursors")],
        },
    },
    "theme": {
        "label": "Tema GTK 3, bordas das janelas e notificações",
        "files": {
            "system": [("Theme/windows-classic", "/usr/share/themes/windows-classic"),
                       ("Theme/windows-classic-xhdpi", "/usr/share/themes/windows-classic-xhdpi")],
            "user": [("Theme/windows-classic", "~/.local/share/themes/windows-classic"),
                     ("Theme/windows-classic-xhdpi", "~/.local/share/themes/windows-classic-xhdpi")],
        },
    },
    "terminal": {
        "label": "Cores do terminal: Prompt de comando e MS-DOS",
        "files": {
            "system": [("Terminal/windows-xp-cmd.theme",
                        "/usr/share/xfce4/terminal/colorschemes/windows-xp-cmd.theme"),
                       ("Terminal/ms-dos.theme", "/usr/share/xfce4/terminal/colorschemes/ms-dos.theme")],
            "user": [("Terminal/windows-xp-cmd.theme",
                      "~/.local/share/xfce4/terminal/colorschemes/windows-xp-cmd.theme"),
                     ("Terminal/ms-dos.theme", "~/.local/share/xfce4/terminal/colorschemes/ms-dos.theme")],
        },
    },
    # Sem arquivos: só aplica as fontes para as quais o tema foi medido.
    "fonts": {
        "label": "Fontes recomendadas: Noto Sans 8",
        "files": {"system": [], "user": []},
    },
    # Também sem arquivos: carrega o perfil do painel pelo xfce4-panel-profiles.
    "panel": {
        "label": "Painel Windows XP (substitui o painel atual)",
        "files": {"system": [], "user": []},
    },
}
FILE_COMPONENTS = [c for c in COMPONENTS if COMPONENTS[c]["files"]["user"]]
SETTINGS_ONLY = [c for c in COMPONENTS if c not in FILE_COMPONENTS]   # sempre aplicados
DEFAULT_OFF = {"panel"}               # desmarcados por padrão
DEFAULT_OFF_APPLY = {"terminal"}      # instala os esquemas, mas não troca as cores do terminal

def dest_path(dest):
    return Path(os.path.expanduser(dest))


def run(cmd, check=False, env=None):
    return subprocess.run(cmd, capture_output=True, text=True, check=check, env=env or CHILD_ENV)


# --------------------------------------------------------------------------
# Cópia de arquivos (usada nos dois modos; no modo sistema roda como root)
# --------------------------------------------------------------------------

def install_files(comp, mode, log):
    for src_rel, dest in COMPONENTS[comp]["files"][mode]:
        src, dest = SRC / src_rel, dest_path(dest)
        if not src.exists():
            raise RuntimeError(f"origem não encontrada: {src}")
        dest.parent.mkdir(parents=True, exist_ok=True)
        if src.is_dir():
            # Copia para .new e troca com rename: o destino quase não fica ausente.
            new, old = dest.with_name(dest.name + ".new"), dest.with_name(dest.name + ".old")
            for p in (new, old):
                if p.exists():
                    shutil.rmtree(p)
            shutil.copytree(src, new, symlinks=True)
            (new / MARK).touch()
            if dest.exists():
                dest.rename(old)
            new.rename(dest)
            if old.exists():
                shutil.rmtree(old)
        else:
            shutil.copy2(src, dest)
        log(f"  {src_rel} → {dest}")


def remove_files(comp, mode, log):
    for _src_rel, dest in COMPONENTS[comp]["files"][mode]:
        dest = dest_path(dest)
        if dest.is_dir() and not dest.is_symlink():
            if (dest / MARK).exists():
                shutil.rmtree(dest)
                log(f"  removido {dest}")
            else:
                log(f"  {dest} mantido (não foi instalado por este instalador)")
        elif dest.exists() or dest.is_symlink():
            dest.unlink()
            log(f"  removido {dest}")


def installed_in(comp, mode):
    files = COMPONENTS[comp]["files"][mode]
    if not files:
        return False
    dest = dest_path(files[0][1])
    return (dest / MARK).exists() if dest.is_dir() else dest.exists()


def root_main(action, comps):
    """Executado pelo pkexec. Só aceita os componentes conhecidos e os destinos fixos acima."""
    if os.geteuid() != 0:
        sys.exit("--root só pode ser usado pelo pkexec")
    os.umask(0o022)
    bad = [c for c in comps if c not in FILE_COMPONENTS]
    if action not in ("install", "uninstall") or bad:
        sys.exit(f"pedido inválido: {action} {bad}")

    def log(msg):
        print(msg, flush=True)

    for comp in comps:
        log(f"{COMPONENTS[comp]['label']}:")
        (install_files if action == "install" else remove_files)(comp, "system", log)


# --------------------------------------------------------------------------
# Configurações do XFCE (sempre como o usuário)
# --------------------------------------------------------------------------

def have_xfce():
    return shutil.which("xfconf-query") is not None


def have_xfce_panel():
    return shutil.which("xfce4-panel-profiles") is not None


def xfconf_get(channel, prop):
    r = run(["xfconf-query", "-c", channel, "-p", prop], env=XFCONF_ENV)
    return r.stdout.strip() if r.returncode == 0 else None


def xfconf_set(channel, prop, kind, value):
    run(["xfconf-query", "-c", channel, "-p", prop, "-n", "-t", kind, "-s", value],
        check=True, env=XFCONF_ENV)


def xfconf_reset(channel, prop):
    run(["xfconf-query", "-c", channel, "-p", prop, "-r"], env=XFCONF_ENV)


def window_scale():
    try:
        return int(xfconf_get("xsettings", "/Gdk/WindowScalingFactor") or 1)
    except ValueError:
        return 1


def terminal_scheme(name="windows-xp-cmd.theme"):
    """Lê um esquema de Terminal/ (formato do xfce4-terminal)."""
    out = {}
    for line in (SRC / "Terminal" / name).read_text().splitlines():
        if "=" in line and not line.startswith("#"):
            k, v = line.split("=", 1)
            out[k.strip()] = v.strip()
    return out


def settings_for(comp):
    """Lista de (canal, propriedade, tipo, valor) que "Aplicar" grava."""
    if comp == "theme":
        wm = f"{NAME}-xhdpi" if window_scale() == 2 else NAME
        return [("xsettings", "/Net/ThemeName", "string", NAME),
                ("xfwm4", "/general/theme", "string", wm),
                ("xfce4-notifyd", "/theme", "string", NAME),
                ("xfce4-notifyd", "/initial-opacity", "double", "1.0"),
                # Sem o "Realce de arquivos", a seleção de ícones fica como no Explorer do XP
                ("thunar", "/misc-highlighting-enabled", "bool", "false")]
    if comp == "cursors":
        size = "64" if window_scale() == 2 else "32"
        return [("xsettings", "/Gtk/CursorThemeName", "string", "windows-classic-cursors"),
                ("xsettings", "/Gtk/CursorThemeSize", "int", size)]
    if comp == "fonts":
        return [("xsettings", "/Gtk/FontName", "string", "Noto Sans 8"),
                ("xfwm4", "/general/title_font", "string", "Noto Sans Bold 8")]
    if comp == "terminal":
        if not shutil.which("xfce4-terminal"):
            return []
        s = terminal_scheme()
        return [("xfce4-terminal", "/color-use-theme", "bool", "false"),
                ("xfce4-terminal", "/color-foreground", "string", s["ColorForeground"]),
                ("xfce4-terminal", "/color-background", "string", s["ColorBackground"]),
                ("xfce4-terminal", "/color-palette", "string", s["ColorPalette"]),
                ("xfce4-terminal", "/color-bold-use-default", "bool", "true"),
                ("xfce4-terminal", "/color-cursor-use-default", "bool", "false"),
                ("xfce4-terminal", "/color-cursor", "string", s["ColorCursor"]),
                ("xfce4-terminal", "/misc-cursor-shape", "string", "TERMINAL_CURSOR_SHAPE_UNDERLINE"),
                ("xfce4-terminal", "/misc-cursor-blinks", "bool", "true")]
    return []


def noto_installed():
    if not shutil.which("fc-list"):
        return True
    return bool(run(["fc-list", "Noto Sans:style=Regular", "family"]).stdout.strip())


def apply_component(comp, log):
    if comp == "panel":
        if not have_xfce_panel():
            log("  xfce4-panel-profiles não encontrado (sudo pacman -S --needed xfce4-panel-profiles);"
                " nada a aplicar")
            return
        run(["xfce4-panel-profiles", "load", str(PANEL_PROFILE)], check=True)
        log("  painel Windows XP carregado")
        return
    if not have_xfce():
        log("  XFCE (xfconf-query) não encontrado; ative o componente nas configurações da área de trabalho")
        return
    items = settings_for(comp)
    if comp == "terminal" and not items:
        log("  o Xfce Terminal não está instalado; nada a aplicar")
    for channel, prop, kind, value in items:
        xfconf_set(channel, prop, kind, value)
        log(f"  {channel} {prop} = {value}")
    if comp == "fonts" and not noto_installed():
        log("  atenção: a fonte Noto Sans não está instalada (sudo pacman -S --needed noto-fonts)")
    if comp == "cursors":
        env = os.environ.get("XCURSOR_THEME")
        if env and env != NAME:
            log(f"  atenção: XCURSOR_THEME={env} na sessão (veja /etc/environment e ~/.profile);"
                " alguns aplicativos continuarão com esse cursor")


def reset_component(comp, log):
    """Ao remover: as configurações do componente voltam ao padrão do XFCE."""
    if comp == "panel":
        log("  o painel não é alterado; para trocar de layout, use Configurações → Painel"
            " ou xfce4-panel-profiles")
        return
    if not have_xfce():
        return
    for channel, prop, _kind, _value in settings_for(comp):
        xfconf_reset(channel, prop)
        log(f"  {channel} {prop}: padrão do XFCE")


def applied(comp):
    """As configurações do componente estão em uso (comparadas com o valor atual)."""
    if comp == "panel" or not have_xfce():
        return False
    items = settings_for(comp)
    if not items:
        return False
    for channel, prop, kind, value in items:
        cur = xfconf_get(channel, prop)
        if kind == "double":
            try:
                if abs(float(cur) - float(value)) > 1e-6:
                    return False
            except (TypeError, ValueError):
                return False
        elif cur != value:
            return False
    return True


# --------------------------------------------------------------------------
# Instalação / desinstalação (como o usuário)
# --------------------------------------------------------------------------

def run_as_root(action, comps, log):
    if not shutil.which("pkexec"):
        raise RuntimeError("pkexec não encontrado (sudo pacman -S --needed polkit)")
    cmd = ["pkexec", sys.executable, "-I", str(Path(__file__).resolve()), "--root", action, *comps]
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                            env=CHILD_ENV)
    for line in proc.stdout:
        log(line.rstrip())
    if proc.wait() in (126, 127):
        raise RuntimeError("autorização negada ou cancelada")
    if proc.returncode:
        raise RuntimeError(f"a cópia como root falhou (código {proc.returncode})")


def do_install(comps, mode, apply, log, progress=lambda f: None):
    if os.geteuid() == 0:
        raise RuntimeError("não rode o instalador como root; use \"Todos os usuários\" (--system)")
    comps = [c for c in COMPONENTS if c in comps]       # ordem fixa
    files = [c for c in comps if c in FILE_COMPONENTS]
    to_apply = [c for c in comps if c in apply or c in SETTINGS_ONLY]
    steps = len(files) + len(to_apply) or 1
    done = 0

    if mode == "system" and files:
        log("Copiando para o sistema (pkexec)...")
        run_as_root("install", files, log)
        done += len(files)
        progress(done / steps)
    else:
        for comp in files:
            log(f"{COMPONENTS[comp]['label']}:")
            install_files(comp, mode, log)
            done += 1
            progress(done / steps)

    for comp in to_apply:
        log(f"Aplicando: {COMPONENTS[comp]['label']}")
        apply_component(comp, log)
        done += 1
        progress(done / steps)
    log("Instalação concluída.")


def do_uninstall(comps, mode, log, progress=lambda f: None):
    if os.geteuid() == 0:
        raise RuntimeError("não rode o instalador como root; use \"Todos os usuários\" (--system)")
    comps = [c for c in COMPONENTS if c in comps]
    steps, done = len(comps) * 2 or 1, 0
    for comp in comps:
        log(f"Configurações padrão: {COMPONENTS[comp]['label']}")
        reset_component(comp, log)
        done += 1
        progress(done / steps)
    files = [c for c in comps if c in FILE_COMPONENTS and installed_in(c, mode)]
    if mode == "system" and files:
        log("Removendo do sistema (pkexec)...")
        run_as_root("uninstall", files, log)
    else:
        for comp in files:
            log(f"{COMPONENTS[comp]['label']}:")
            remove_files(comp, mode, log)
    progress(1)
    log("Desinstalação concluída.")


def status_text(comp):
    if comp == "panel":
        return "" if have_xfce_panel() else "xfce4-panel-profiles não encontrado"
    if comp in SETTINGS_ONLY:
        return "aplicado" if applied(comp) else ""
    where = [n for m, n in (("user", "usuário"), ("system", "sistema")) if installed_in(comp, m)]
    return " + ".join(where) if where else "não instalado"


# --------------------------------------------------------------------------
# Janela: assistente no estilo dos assistentes do Windows XP
# --------------------------------------------------------------------------

TITLE = "Instalação do tema Windows Classic"

DESCRIPTIONS = {
    "cursors": "Ponteiros do mouse originais do Windows XP, em 32, 64 e 96 px.",
    "theme": "Janelas, botões, menus e barras de rolagem do Windows XP clássico para GTK 3, "
             "bordas das janelas do xfwm4 (normal e HiDPI) e balões de notificação.",
    "terminal": "Esquemas de cores do xfce4-terminal: Prompt de comando do Windows XP e "
                "MS-DOS. \"Aplicar\" troca as cores do terminal pelas do Prompt de comando; "
                "ao remover, voltam as cores padrão do Xfce Terminal.",
    "fonts": "Noto Sans 8 na interface e Noto Sans Bold 8 nos títulos das janelas: as fontes "
             "para as quais o tema foi medido. Ao remover, voltam as fontes padrão do XFCE.",
    "panel": "Barra de tarefas no estilo do Windows XP: botão Iniciar (Whisker Menu), "
             "Inicialização rápida, lista de janelas, área de notificação e relógio. Substitui o "
             "painel atual (sem backup).",
}

# Logotipo do assistente: a bandeira de 38x38 do Windows XP (shell32.dll, bitmap 242,
# primeiro quadro), em PNG embutido para o instalador ser um arquivo só.
LOGO_PNG = (
    "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"
)

# Faixa branca do topo, como nos assistentes do Windows XP
WIZARD_CSS = b"""
.wc-setup-banner {
  background-color: #ffffff; }
.wc-setup-banner label {
  color: #000000; }
"""


def use_project_theme():
    """A janela usa sempre o tema do projeto, qualquer que seja o tema do sistema. Um link com
    nome próprio numa pasta temporária, colocada no XDG_DATA_DIRS antes de o GTK iniciar, evita
    que uma cópia já instalada (talvez antiga) seja usada no lugar."""
    tmp = Path(tempfile.mkdtemp(prefix="windows-classic-setup-", dir=os.environ.get("XDG_RUNTIME_DIR")))
    atexit.register(shutil.rmtree, tmp, True)
    (tmp / "themes").mkdir()
    (tmp / "themes" / "windows-classic-setup").symlink_to(SRC / "Theme" / NAME)
    os.environ["XDG_DATA_DIRS"] = f"{tmp}:" + os.environ.get("XDG_DATA_DIRS", "/usr/local/share:/usr/share")
    os.environ["GTK_THEME"] = "windows-classic-setup"


def gui_main():
    use_project_theme()
    import gi
    gi.require_version("Gtk", "3.0")
    gi.require_version("Gdk", "3.0")
    from gi.repository import Gdk, GdkPixbuf, GLib, Gtk, Pango

    def bold(text, size=None):
        lbl = Gtk.Label(xalign=0, wrap=True, max_width_chars=60)
        size_attr = f" size='{size}'" if size else ""
        lbl.set_markup(f"<span weight='bold'{size_attr}>{GLib.markup_escape_text(text)}</span>")
        return lbl

    def text(content):
        return Gtk.Label(label=content, xalign=0, wrap=True, max_width_chars=60)

    def page(title, subtitle=None, big=False):
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        box.pack_start(bold(title, "large" if big else None), False, False, 0)
        if subtitle is not None:
            sub = text(subtitle)
            sub.set_margin_start(0 if big else 12)
            box.pack_start(sub, False, False, 0)
        return box

    class Wizard(Gtk.Window):
        def __init__(self):
            super().__init__(title=TITLE)
            self.set_icon_name("system-software-install")
            self.set_resizable(False)
            self.set_position(Gtk.WindowPosition.CENTER)
            self.busy = False
            self.finished = False

            provider = Gtk.CssProvider()
            provider.load_from_data(WIZARD_CSS)
            Gtk.StyleContext.add_provider_for_screen(
                Gdk.Screen.get_default(), provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)

            dialog = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
            dialog.set_size_request(560, 470)   # fixo: não muda de tamanho entre as páginas
            self.add(dialog)

            # Faixa branca com o título e a bandeira do XP, como nos assistentes do XP
            banner = Gtk.EventBox()
            banner.get_style_context().add_class("wc-setup-banner")
            row = Gtk.Box(spacing=12, margin_start=16, margin_end=16, margin_top=10, margin_bottom=10)
            texts = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2, valign=Gtk.Align.CENTER)
            texts.pack_start(bold("Windows Classic", "large"), False, False, 0)
            texts.pack_start(text("Tema do Windows XP clássico para o XFCE"), False, False, 0)
            row.pack_start(texts, True, True, 0)
            loader = GdkPixbuf.PixbufLoader.new_with_type("png")
            loader.write(base64.b64decode(LOGO_PNG))
            loader.close()
            row.pack_end(Gtk.Image.new_from_pixbuf(loader.get_pixbuf()), False, False, 0)
            banner.add(row)
            dialog.pack_start(banner, False, False, 0)
            dialog.pack_start(Gtk.Separator(), False, False, 0)

            self.stack = Gtk.Stack(transition_type=Gtk.StackTransitionType.NONE)
            for m in ("start", "end", "top", "bottom"):
                getattr(self.stack, f"set_margin_{m}")(16 if m in ("start", "end") else 12)
            dialog.pack_start(self.stack, True, True, 0)
            dialog.pack_start(Gtk.Separator(), False, False, 0)

            buttons = Gtk.Box(spacing=6, margin=8, halign=Gtk.Align.END)
            self.back_btn = Gtk.Button.new_with_mnemonic("< _Voltar")
            self.next_btn = Gtk.Button.new_with_mnemonic("_Avançar >")
            self.cancel_btn = Gtk.Button.new_with_mnemonic("Cancelar")
            for b in (self.back_btn, self.next_btn, self.cancel_btn):
                b.set_size_request(80, -1)
            self.next_btn.set_can_default(True)
            self.back_btn.connect("clicked", lambda _b: self.go(-1))
            self.next_btn.connect("clicked", lambda _b: self.go(+1))
            self.cancel_btn.connect("clicked", lambda _b: self.close())
            buttons.pack_start(self.back_btn, False, False, 0)
            buttons.pack_start(self.next_btn, False, False, 6)
            buttons.pack_start(self.cancel_btn, False, False, 0)
            dialog.pack_start(buttons, False, False, 0)

            self.buffer = Gtk.TextBuffer()
            self.end_mark = self.buffer.create_mark(None, self.buffer.get_end_iter(), False)
            self.views = []

            self.build_welcome()
            self.build_type()
            self.build_components()
            self.build_ready()
            self.build_progress()
            self.build_finish()
            self.current = "welcome"
            self.connect("delete-event", self.on_delete)
            self.show_page()

        # Páginas -----------------------------------------------------------

        def build_welcome(self):
            box = page("Bem-vindo ao Assistente de instalação do tema Windows Classic", big=True)
            box.pack_start(text(
                "Este assistente instala o visual clássico do Windows XP no XFCE: janelas, "
                "bordas, cursores, notificações, cores do terminal e fontes.\n\n"
                "Você escolhe os componentes e se a instalação vale só para você ou para "
                "todos os usuários deste computador. O assistente também remove o tema e "
                "volta às configurações padrão do XFCE.\n\n"
                "Para continuar, clique em Avançar."), False, False, 8)
            self.stack.add_named(box, "welcome")

        def build_type(self):
            box = page("Tipo de instalação", "Escolha o que fazer e para quem.")
            frame = Gtk.Frame(label="Operação")
            inner = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4, border_width=8)
            self.op_install = Gtk.RadioButton.new_with_mnemonic(None, "_Instalar ou atualizar componentes")
            self.op_remove = Gtk.RadioButton.new_with_mnemonic_from_widget(self.op_install,
                                                                           "_Remover componentes")
            inner.pack_start(self.op_install, False, False, 0)
            inner.pack_start(self.op_remove, False, False, 0)
            frame.add(inner)
            box.pack_start(frame, False, False, 4)

            frame = Gtk.Frame(label="Instalar para")
            inner = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4, border_width=8)
            self.mode_user = Gtk.RadioButton.new_with_mnemonic(None, "_Somente para mim")
            self.mode_system = Gtk.RadioButton.new_with_mnemonic_from_widget(
                self.mode_user, "_Todos os usuários deste computador")
            inner.pack_start(self.mode_user, False, False, 0)
            inner.pack_start(self.mode_system, False, False, 0)
            note = text("A instalação para todos os usuários copia os arquivos para /usr/share "
                        "e pede a senha de administrador.")
            note.set_margin_start(24)
            inner.pack_start(note, False, False, 0)
            frame.add(inner)
            box.pack_start(frame, False, False, 4)
            self.stack.add_named(box, "type")

        def build_components(self):
            self.comp_box = page("Componentes", "")
            self.store = Gtk.ListStore(bool, str, bool, bool, str, str)
            view = Gtk.TreeView(model=self.store, headers_visible=True)
            col = Gtk.TreeViewColumn("Componente")
            toggle = Gtk.CellRendererToggle()
            toggle.connect("toggled", self.on_toggle, 0)
            col.pack_start(toggle, False)
            col.add_attribute(toggle, "active", 0)
            label = Gtk.CellRendererText()
            col.pack_start(label, True)
            col.add_attribute(label, "text", 1)
            col.set_expand(True)
            view.append_column(col)
            self.apply_toggle = Gtk.CellRendererToggle()
            self.apply_toggle.connect("toggled", self.on_toggle, 2)
            self.apply_col = Gtk.TreeViewColumn("Aplicar", self.apply_toggle, active=2, visible=3,
                                                sensitive=0, activatable=0)
            view.append_column(self.apply_col)
            view.append_column(Gtk.TreeViewColumn("Situação", Gtk.CellRendererText(), text=4))
            scroll = Gtk.ScrolledWindow(min_content_height=120)
            scroll.set_shadow_type(Gtk.ShadowType.IN)
            scroll.add(view)
            self.comp_box.pack_start(scroll, True, True, 0)

            frame = Gtk.Frame(label="Descrição")
            self.desc = text("")
            self.desc.set_margin_start(8)
            self.desc.set_margin_end(8)
            self.desc.set_margin_bottom(6)
            self.desc.set_size_request(-1, 52)
            self.desc.set_valign(Gtk.Align.START)
            frame.add(self.desc)
            self.comp_box.pack_start(frame, False, False, 0)
            view.get_selection().connect("changed", self.on_select)
            self.comp_view = view
            for comp in COMPONENTS:
                self.store.append([False, COMPONENTS[comp]["label"], False,
                                   comp not in SETTINGS_ONLY, "", comp])
            self.stack.add_named(self.comp_box, "components")

        def build_ready(self):
            self.ready_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
            self.ready_title = bold("")
            self.ready_text = text("")
            self.ready_list = text("")
            self.ready_list.set_margin_start(16)
            self.ready_warn = text("")
            for w in (self.ready_title, self.ready_text, self.ready_list, self.ready_warn):
                self.ready_box.pack_start(w, False, False, 0)
            self.stack.add_named(self.ready_box, "ready")

        def log_view(self):
            view = Gtk.TextView(buffer=self.buffer, editable=False, cursor_visible=False,
                                wrap_mode=Gtk.WrapMode.WORD_CHAR)
            scroll = Gtk.ScrolledWindow(min_content_height=110)
            scroll.set_shadow_type(Gtk.ShadowType.IN)
            scroll.add(view)
            self.views.append(view)
            return scroll

        def build_progress(self):
            self.progress_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
            self.progress_title = bold("")
            self.progress_box.pack_start(self.progress_title, False, False, 0)
            self.status = text("Preparando...")
            self.status.set_ellipsize(Pango.EllipsizeMode.END)
            self.status.set_line_wrap(False)
            self.progress_box.pack_start(self.status, False, False, 8)
            self.progress = Gtk.ProgressBar()
            self.progress_box.pack_start(self.progress, False, False, 0)
            exp = Gtk.Expander(label="_Detalhes", use_underline=True)
            exp.add(self.log_view())
            self.progress_box.pack_start(exp, True, True, 8)
            self.stack.add_named(self.progress_box, "progress")

        def build_finish(self):
            self.finish_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
            self.finish_title = bold("", "large")
            self.finish_text = text("")
            self.finish_box.pack_start(self.finish_title, False, False, 0)
            self.finish_box.pack_start(self.finish_text, False, False, 8)
            # Como no Setup do Windows: reiniciar agora ou depois.
            self.reboot_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
            self.reboot_now = Gtk.RadioButton.new_with_mnemonic(
                None, "_Sim, desejo reiniciar o computador agora.")
            self.reboot_later = Gtk.RadioButton.new_with_mnemonic_from_widget(
                self.reboot_now, "_Não, reiniciarei o computador mais tarde.")
            self.reboot_later.set_active(True)
            for w in (self.reboot_now, self.reboot_later):
                self.reboot_box.pack_start(w, False, False, 0)
            self.finish_box.pack_start(self.reboot_box, False, False, 0)
            self.finish_exp = Gtk.Expander(label="_Detalhes", use_underline=True)
            self.finish_exp.add(self.log_view())
            self.finish_box.pack_start(self.finish_exp, True, True, 0)
            self.stack.add_named(self.finish_box, "finish")

        # Estado ------------------------------------------------------------

        @property
        def removing(self):
            return self.op_remove.get_active()

        @property
        def mode(self):
            return "system" if self.mode_system.get_active() else "user"

        def selected(self, col=0):
            return [row[5] for row in self.store if row[col]]

        def pages(self):
            return ["welcome", "type", "components", "ready", "progress", "finish"]

        def fill_components(self):
            removing = self.removing
            for row in self.store:
                comp = row[5]
                if removing:
                    row[0] = applied(comp) if comp in SETTINGS_ONLY else installed_in(comp, self.mode)
                else:
                    row[0] = comp not in DEFAULT_OFF
                    row[2] = comp not in SETTINGS_ONLY and comp not in DEFAULT_OFF_APPLY
                row[4] = status_text(comp)
            self.apply_col.set_visible(not removing)
            subtitle = self.comp_box.get_children()[1]
            subtitle.set_text(
                "Marque os componentes a remover. As configurações deles voltam ao padrão do XFCE."
                if removing else
                "Marque os componentes a instalar. \"Aplicar\" ativa o componente no XFCE "
                "logo após a cópia.")
            self.comp_view.get_selection().select_path(Gtk.TreePath.new_first())

        def on_toggle(self, _cell, path, col):
            self.store[path][col] = not self.store[path][col]
            self.update_buttons()

        def on_select(self, selection):
            model, it = selection.get_selected()
            if it:
                self.desc.set_text(DESCRIPTIONS.get(model[it][5], ""))

        def fill_ready(self):
            removing = self.removing
            comps = self.selected()
            system = self.mode == "system"
            if removing:
                self.ready_title.set_markup("<b>Pronto para remover</b>")
                self.ready_text.set_text(
                    "O assistente vai remover "
                    + ("da instalação para todos os usuários (/usr/share):" if system
                       else "da instalação na sua pasta pessoal:"))
            else:
                self.ready_title.set_markup("<b>Pronto para instalar</b>")
                self.ready_text.set_text(
                    "O assistente vai instalar "
                    + ("para todos os usuários (/usr/share):" if system
                       else "somente para você (pasta pessoal):"))
            apply = set(self.selected(2))
            self.ready_list.set_text("\n".join(
                f"•  {COMPONENTS[c]['label']}"
                + ("  (aplicar)" if c in apply and not removing else "") for c in comps))
            warn = []
            if "terminal" in apply and not removing:
                warn.append("As cores do Xfce Terminal serão trocadas pelas do Prompt de comando.")
            if "panel" in comps:
                warn.append("O painel atual do XFCE será substituído (sem backup)."
                            if not removing else
                            "O painel não é alterado na remoção; para trocar de layout, use "
                            "Configurações → Painel.")
            if self.mode == "system":
                warn.append("Será pedida a senha de administrador.")
            warn.append(f"Clique em {'Remover' if removing else 'Instalar'} para começar, "
                        "ou em Voltar para rever as opções.")
            self.ready_warn.set_text("\n\n".join(warn))

        # Navegação ---------------------------------------------------------

        def show_page(self):
            self.stack.set_visible_child_name(self.current)
            self.update_buttons()

        def update_buttons(self):
            name = self.current
            self.back_btn.set_sensitive(name in ("type", "components", "ready"))
            self.cancel_btn.set_sensitive(name not in ("progress", "finish"))
            ok = name != "progress"
            if name == "components":
                ok = bool(self.selected())
            self.next_btn.set_sensitive(ok)
            label = {"ready": "_Remover" if self.removing else "_Instalar",
                     "finish": "_Concluir"}.get(name, "_Avançar >")
            self.next_btn.set_label(label)
            self.next_btn.grab_default()

        def go(self, step):
            name = self.current
            if name == "finish":
                if self.reboot_box.get_visible() and self.reboot_now.get_active():
                    subprocess.Popen(["systemctl", "reboot"], env=CHILD_ENV, start_new_session=True)
                self.destroy()
                return
            if step > 0 and name == "type":
                self.fill_components()
            seq = self.pages()
            self.current = seq[seq.index(name) + step]
            if self.current == "ready":
                self.fill_ready()
            self.show_page()
            if self.current == "progress":
                self.start()

        def on_delete(self, *_):
            if self.busy:
                return True
            if self.finished or self.current == "finish":
                return False
            d = Gtk.MessageDialog(transient_for=self, modal=True, message_type=Gtk.MessageType.QUESTION,
                                  buttons=Gtk.ButtonsType.YES_NO, text=TITLE,
                                  secondary_text="Tem certeza de que deseja cancelar a instalação?")
            ok = d.run() == Gtk.ResponseType.YES
            d.destroy()
            return not ok

        # Execução ----------------------------------------------------------

        def log(self, msg):
            def add():
                self.buffer.insert(self.buffer.get_end_iter(), msg + "\n")
                for v in self.views:
                    v.scroll_mark_onscreen(self.end_mark)
                if msg and not msg.startswith(" "):
                    self.status.set_text(msg)
            GLib.idle_add(add)

        def set_progress(self, fraction):
            GLib.idle_add(self.progress.set_fraction, fraction)

        def start(self):
            removing, mode = self.removing, self.mode
            comps, apply = self.selected(), self.selected(2)
            self.progress_title.set_markup(
                f"<b>{'Removendo' if removing else 'Instalando'} o tema Windows Classic</b>")
            self.busy = True
            self.update_buttons()

            def work():
                try:
                    if removing:
                        do_uninstall(comps, mode, self.log, self.set_progress)
                    else:
                        do_install(comps, mode, apply, self.log, self.set_progress)
                    error = None
                except Exception as e:  # mostra qualquer falha na página final
                    self.log(f"ERRO: {e}")
                    error = str(e)
                GLib.idle_add(self.done, removing, error)

            threading.Thread(target=work, daemon=True).start()

        def done(self, removing, error):
            self.busy = False
            self.finished = True
            if error:
                self.finish_title.set_markup("<span weight='bold' size='large'>"
                                             "O assistente não foi concluído</span>")
                self.finish_text.set_text(f"Ocorreu um erro: {error}\n\nVeja os detalhes abaixo. "
                                          "Nenhuma configuração foi aplicada depois do erro.")
                self.finish_exp.set_expanded(True)
                self.reboot_box.hide()
            else:
                verb = "removido" if removing else "instalado"
                self.finish_title.set_markup("<span weight='bold' size='large'>Concluindo o Assistente "
                                             "de instalação do tema Windows Classic</span>")
                extra = ("" if removing else
                         "\n\nAlguns aplicativos abertos só mudam de aparência depois de reabertos. "
                         "Os cursores podem exigir sair e entrar de novo na sessão.")
                self.finish_text.set_text(f"O tema Windows Classic foi {verb} com êxito.{extra}"
                                          "\n\nPara ver todas as mudanças, reinicie o computador. "
                                          "Para fechar o assistente, clique em Concluir.")
                self.reboot_box.show_all()
            self.current = "finish"
            self.show_page()

    win = Wizard()
    win.connect("destroy", Gtk.main_quit)
    # Encerrar por sinal (Ctrl+C, kill) também sai pelo laço do GTK, para o atexit apagar a
    # pasta temporária do tema. GLibUnix.signal_add só existe no GLib 2.84+.
    signal_add = None
    try:
        gi.require_version("GLibUnix", "2.0")
        from gi.repository import GLibUnix
        signal_add = getattr(GLibUnix, "signal_add", None)
    except (ValueError, ImportError):
        pass
    if signal_add is None:
        signal_add = GLib.unix_signal_add
    for sig in (signal.SIGINT, signal.SIGTERM):
        signal_add(GLib.PRIORITY_DEFAULT, sig, Gtk.main_quit)
    win.show_all()
    Gtk.main()


# --------------------------------------------------------------------------

def parse_list(value):
    if value == "all":
        return [c for c in COMPONENTS if c not in DEFAULT_OFF]
    comps = [c.strip() for c in value.split(",") if c.strip()]
    bad = [c for c in comps if c not in COMPONENTS]
    if bad:
        raise argparse.ArgumentTypeError(f"componente desconhecido: {', '.join(bad)}"
                                          f" (use: {', '.join(COMPONENTS)})")
    return comps


def main():
    ap = argparse.ArgumentParser(description="Instalador do tema Windows Classic para XFCE.")
    ap.add_argument("--list", action="store_true", help="lista os componentes e onde estão instalados")
    ap.add_argument("--install", type=parse_list, metavar="LISTA",
                    help=f"'all' ou componentes separados por vírgula: {','.join(COMPONENTS)}")
    ap.add_argument("--uninstall", type=parse_list, metavar="LISTA", help="idem, para remover")
    ap.add_argument("--system", action="store_true", help="instala em /usr/share (pede senha pelo pkexec)")
    ap.add_argument("--no-apply", action="store_true", help="só copia, não ativa no XFCE")
    ap.add_argument("--apply-terminal", action="store_true",
                    help="também troca as cores do Xfce Terminal pelas do Prompt de comando")
    ap.add_argument("--with-panel", action="store_true",
                    help="também carrega o painel Windows XP (substitui o painel atual)")
    ap.add_argument("--root", nargs="+", help=argparse.SUPPRESS)
    args = ap.parse_args()

    if args.root:
        root_main(args.root[0], args.root[1:])
        return

    mode = "system" if args.system else "user"
    try:
        if args.list:
            for comp in COMPONENTS:
                print(f"{comp:10} {COMPONENTS[comp]['label']:50} {status_text(comp)}")
        elif args.install:
            if args.with_panel and "panel" not in args.install:
                args.install.append("panel")
            apply = [] if args.no_apply else [c for c in args.install
                                               if c not in DEFAULT_OFF_APPLY or args.apply_terminal]
            do_install(args.install, mode, apply, print)
        elif args.uninstall:
            do_uninstall(args.uninstall, mode, print)
        elif os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY"):
            gui_main()
        else:
            ap.print_help()
    except (RuntimeError, subprocess.CalledProcessError, OSError) as e:
        sys.exit(f"Erro: {e}")


if __name__ == "__main__":
    main()
