#!/usr/bin/env bash

python3 /home/eu/Desktop/windows-classic-xfce/Icons/src/aplicar-lista.py
python3 /home/eu/Desktop/windows-classic-xfce/Icons/src/mapa.py

sudo rm -rf /usr/share/icons/windows-classic-icons
sudo cp -r windows-classic-icons /usr/share/icons
sudo gtk-update-icon-cache -f -t /usr/share/icons/windows-classic-icons
