#!/usr/bin/env bash
# Gera pastas WxH a partir de 1024x1024 conforme sizes.txt
# Uso: ./resize.sh [--skip]
#   --skip  mantém as pastas existentes e só gera as imagens que ainda não existem
cd "$(dirname "$0")" || exit 1
SRC="1024x1024"
SKIP=0
for arg in "$@"; do
  case "$arg" in
    --skip) SKIP=1 ;;
    -h|--help) sed -n '2,4p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) echo "Parâmetro desconhecido: $arg (use --skip)"; exit 1 ;;
  esac
done
export SKIP
while IFS= read -r line || [ -n "$line" ]; do
  size="$(echo "$line" | tr -d '[:space:]')"
  [ -z "$size" ] && continue
  [[ "$size" == "$SRC" ]] && continue
  [[ "$size" =~ ^[0-9]+$ ]] && size="${size}x${size}"
  if ! [[ "$size" =~ ^[0-9]+x[0-9]+$ ]]; then echo "Ignorando linha inválida: $line"; continue; fi
  if [ "$SKIP" = 1 ]; then
    echo "Gerando $size (pulando existentes)..."
    mkdir -p "$size"
  else
    rm -rf "$size"; mkdir -p "$size"
    echo "Gerando $size..."
  fi
  find "$SRC" -maxdepth 1 -type f -iname '*.png' -print0 |
    xargs -0 -P"$(nproc)" -I{} bash -c '[ "$SKIP" = 1 ] && [ -e "$2/$(basename "$1")" ] && exit 0; magick -quiet "$1" -strip -filter Lanczos -resize "$2" -background none -gravity center -extent "$2" "$2/$(basename "$1")"' _ {} "$size"
done < sizes.txt
echo "Pronto."
