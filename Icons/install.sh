#!/usr/bin/env bash

# Aplicar Lista
python3 aplicar-lista.py --forcar

# Regenerar o mapeador a partir dos icones
python3 mapa.py

# Remover icones antigos
sudo rm -rf /usr/share/icons/windows-classic-icons

# Instalar novos icones
sudo cp -r windows-classic-icons /usr/share/icons

# Atualizar cache dos novos icones
sudo gtk-update-icon-cache -f -t /usr/share/icons/windows-classic-icons

# Reiniciar Thunar
thunar -q

# Reiniciar Painel
xfce4-panel -r
