#!/usr/bin/env bash
# Abre uma sessão XFCE de testes dentro de uma janela Xephyr, usando o tema
# direto desta pasta (sem instalar nada e sem mexer nas suas configurações).
#
# Dependência (Arch Linux):  sudo pacman -S --needed xorg-server-xephyr
#
# Uso: ./testar.sh [resolução] [escala]
#   ex.: ./testar.sh 1280x800
#        ./testar.sh 1920x1080 2     (HiDPI: escala de janelas 2x, usa xfwm4_hidpi)
set -euo pipefail

AQUI="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RES="${1:-1024x768}"
ESCALA="${2:-1}"

command -v Xephyr >/dev/null || {
    echo "Xephyr não encontrado. Instale com: sudo pacman -S --needed xorg-server-xephyr"
    exit 1
}
[[ -e "$AQUI/Cursors/windows-classic-cursors/cursors/default" ]] || {
    echo "Gere os cursores antes: python3 Cursors/src/build.py /caminho/I386"
    exit 1
}

# Primeiro display livre a partir do :2
TELA=2
while [[ -e "/tmp/.X11-unix/X$TELA" || -e "/tmp/.X$TELA-lock" ]]; do
    TELA=$((TELA + 1))
done

# Perfil temporário: a sessão de teste tem suas próprias configurações do XFCE
PERFIL="$(mktemp -d -t windows-classic-teste.XXXXXX)"
trap 'kill "${XEPHYR:-}" 2>/dev/null || true; rm -rf "$PERFIL"' EXIT

XML="$PERFIL/config/xfce4/xfconf/xfce-perchannel-xml"
mkdir -p "$XML" "$PERFIL/icons" "$PERFIL/themes"
ln -s "$AQUI/Cursors/windows-classic-cursors" "$PERFIL/icons/windows-classic-cursors"
ln -s "$AQUI/Icons/windows-classic-icons" "$PERFIL/icons/windows-classic-icons"
ln -s "$AQUI/Theme/windows-classic" "$PERFIL/themes/windows-classic"
ln -s "$AQUI/Theme/windows-classic-xhdpi" "$PERFIL/themes/windows-classic-xhdpi"

# Esquemas de cores do xfce4-terminal
mkdir -p "$PERFIL/xfce4/terminal/colorschemes"
cp "$AQUI"/Terminal/*.theme "$PERFIL/xfce4/terminal/colorschemes/"

# Na escala 2x as bordas usam a variante HiDPI do tema xfwm4
TEMA_WM="windows-classic"
[[ "$ESCALA" == 2 ]] && TEMA_WM="windows-classic-xhdpi"

cat > "$XML/xsettings.xml" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<channel name="xsettings" version="1.0">
  <property name="Gtk" type="empty">
    <property name="CursorThemeName" type="string" value="windows-classic-cursors"/>
    <property name="CursorThemeSize" type="int" value="$((32 * ESCALA))"/>
    <property name="FontName" type="string" value="Noto Sans 8"/>
  </property>
  <property name="Net" type="empty">
    <property name="ThemeName" type="string" value="windows-classic"/>
    <property name="IconThemeName" type="string" value="windows-classic-icons"/>
  </property>
  <property name="Gdk" type="empty">
    <property name="WindowScalingFactor" type="int" value="$ESCALA"/>
  </property>
  <property name="Xft" type="empty">
    <property name="DPI" type="int" value="96"/>
  </property>
</channel>
EOF

# Thunar: "Realce de arquivos" desligado, para a seleção de ícones no estilo do XP
cat > "$XML/thunar.xml" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<channel name="thunar" version="1.0">
  <property name="misc-highlighting-enabled" type="bool" value="false"/>
</channel>
EOF

# Notificações: tema windows-classic, opacas e no canto inferior direito (como os balões do XP)
cat > "$XML/xfce4-notifyd.xml" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<channel name="xfce4-notifyd" version="1.0">
  <property name="theme" type="string" value="windows-classic"/>
  <property name="initial-opacity" type="double" value="1"/>
  <property name="notify-location" type="uint" value="3"/>
</channel>
EOF

cat > "$XML/xfwm4.xml" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<channel name="xfwm4" version="1.0">
  <property name="general" type="empty">
    <property name="theme" type="string" value="$TEMA_WM"/>
    <property name="title_font" type="string" value="Noto Sans Bold 8"/>
    <property name="use_compositing" type="bool" value="true"/>
  </property>
</channel>
EOF

# Usa uma cópia do seu painel do XFCE (se houver), para testar o tema no painel real
PAINEL="${XDG_CONFIG_HOME:-$HOME/.config}/xfce4"
if [[ -e "$PAINEL/xfconf/xfce-perchannel-xml/xfce4-panel.xml" ]]; then
    cp "$PAINEL/xfconf/xfce-perchannel-xml/xfce4-panel.xml" "$XML/"
    [[ -d "$PAINEL/panel" ]] && cp -r "$PAINEL/panel" "$PERFIL/config/xfce4/"
fi

Xephyr ":$TELA" -screen "$RES" -resizeable -title "Teste: Windows Classic" &
XEPHYR=$!
sleep 1

echo "Sessão de teste no display :$TELA (feche a janela do Xephyr para sair)."
env -i HOME="$HOME" USER="$USER" PATH="$PATH" LANG="${LANG:-pt_BR.UTF-8}" \
    DISPLAY=":$TELA" \
    XDG_CONFIG_HOME="$PERFIL/config" \
    XDG_DATA_HOME="$PERFIL" \
    XDG_CACHE_HOME="$PERFIL/cache" \
    XCURSOR_PATH="$PERFIL/icons:$HOME/.local/share/icons:/usr/share/icons" \
    XCURSOR_THEME="windows-classic-cursors" XCURSOR_SIZE=$((32 * ESCALA)) \
    GTK_OVERLAY_SCROLLING=0 \
    dbus-run-session -- xfce4-session || true
