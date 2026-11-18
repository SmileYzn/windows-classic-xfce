#!/usr/bin/env bash
# Gera pastas WxH a partir de 1024x1024 conforme sizes.txt
cd "$(dirname "$0")" || exit 1
SRC="1024x1024"
while IFS= read -r line || [ -n "$line" ]; do
  size="$(echo "$line" | tr -d '[:space:]')"
  [ -z "$size" ] && continue
  [[ "$size" == "$SRC" ]] && continue
  [[ "$size" =~ ^[0-9]+$ ]] && size="${size}x${size}"
  if ! [[ "$size" =~ ^[0-9]+x[0-9]+$ ]]; then echo "Ignorando linha inválida: $line"; continue; fi
  rm -rf "$size"; mkdir -p "$size"
  echo "Gerando $size..."
  find "$SRC" -maxdepth 1 -type f -iname '*.png' -print0 |
    xargs -0 -P"$(nproc)" -I{} bash -c 'magick -quiet "$1" -strip -filter Lanczos -resize "$2" -background none -gravity center -extent "$2" "$2/$(basename "$1")"' _ {} "$size"
done < sizes.txt
echo "Pronto."
