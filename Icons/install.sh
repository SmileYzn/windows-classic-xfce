#!/usr/bin/env bash

sudo rm -rf /usr/share/icons/windows-classic-icons
sudo cp -r windows-classic-icons /usr/share/icons
sudo gtk-update-icon-cache -f -t /usr/share/icons/windows-classic-icons
