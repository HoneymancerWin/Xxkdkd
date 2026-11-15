#!/data/data/com.termux/files/usr/bin/bash
# Оформление Termux: цветовая тема, удобные клавиши, приветствие со статусом бота.
# Использование: bash termux-theme.sh [mocha|dracula|nord|tokyo|default]
DIR="$(cd "$(dirname "$0")" && pwd)"
THEME="${1:-mocha}"
mkdir -p "$HOME/.termux"

case "$THEME" in
  mocha)   # Catppuccin Mocha — мягкая тёмная
    C="background=#1e1e2e foreground=#cdd6f4 cursor=#f5e0dc
color0=#45475a color1=#f38ba8 color2=#a6e3a1 color3=#f9e2af color4=#89b4fa color5=#f5c2e7 color6=#94e2d5 color7=#bac2de
color8=#585b70 color9=#f38ba8 color10=#a6e3a1 color11=#f9e2af color12=#89b4fa color13=#f5c2e7 color14=#94e2d5 color15=#a6adc8" ;;
  dracula) # Dracula — контрастная фиолетовая
    C="background=#282a36 foreground=#f8f8f2 cursor=#f8f8f2
color0=#21222c color1=#ff5555 color2=#50fa7b color3=#f1fa8c color4=#bd93f9 color5=#ff79c6 color6=#8be9fd color7=#f8f8f2
color8=#6272a4 color9=#ff6e6e color10=#69ff94 color11=#ffffa5 color12=#d6acff color13=#ff92df color14=#a4ffff color15=#ffffff" ;;
  nord)    # Nord — холодная синеватая
    C="background=#2e3440 foreground=#d8dee9 cursor=#d8dee9
color0=#3b4252 color1=#bf616a color2=#a3be8c color3=#ebcb8b color4=#81a1c1 color5=#b48ead color6=#88c0d0 color7=#e5e9f0
color8=#4c566a color9=#bf616a color10=#a3be8c color11=#ebcb8b color12=#81a1c1 color13=#b48ead color14=#8fbcbb color15=#eceff4" ;;
  tokyo)   # Tokyo Night — неоновая ночная
    C="background=#1a1b26 foreground=#c0caf5 cursor=#c0caf5
color0=#15161e color1=#f7768e color2=#9ece6a color3=#e0af68 color4=#7aa2f7 color5=#bb9af7 color6=#7dcfff color7=#a9b1d6
color8=#414868 color9=#f7768e color10=#9ece6a color11=#e0af68 color12=#7aa2f7 color13=#bb9af7 color14=#7dcfff color15=#c0caf5" ;;
  default) rm -f "$HOME/.termux/colors.properties"; C="" ;;
  *) echo "Темы: mocha, dracula, nord, tokyo, default"; exit 1 ;;
esac
[ -n "$C" ] && echo "$C" | tr ' ' '\n' > "$HOME/.termux/colors.properties"

# Удобный ряд клавиш над клавиатурой (Ctrl, стрелки, Tab…)
PROPS="$HOME/.termux/termux.properties"
if ! grep -q "^extra-keys" "$PROPS" 2>/dev/null; then
  cat >> "$PROPS" <<'EOF'
extra-keys = [['ESC','/','-','HOME','UP','END','PGUP'],['TAB','CTRL','ALT','LEFT','DOWN','RIGHT','PGDN']]
EOF
fi

# Вместо стандартного текста Termux — своё приветствие со статусом бота
touch "$HOME/.hushlogin"
RC="$HOME/.bashrc"
touch "$RC"
sed -i '/# >>> avito-banner >>>/,/# <<< avito-banner <<</d' "$RC"
cat >> "$RC" <<EOF
# >>> avito-banner >>>
avito_banner() {
  local c='\e[38;5;117m' g='\e[38;5;114m' r='\e[38;5;210m' d='\e[2m' b='\e[1m' n='\e[0m'
  echo
  echo -e "  \${c}╭──────────────────────╮\${n}"
  echo -e "  \${c}│\${n}  🛒 \${b}AVITO MONITOR\${n}    \${c}│\${n}"
  echo -e "  \${c}╰──────────────────────╯\${n}"
  echo -e "  \${d}охота за выгодными ценами\${n}"
  if [ -f "$DIR/avito.pid" ] && kill -0 \$(cat "$DIR/avito.pid") 2>/dev/null; then
    echo -e "  \${g}●\${n} бот работает"
  else
    echo -e "  \${r}●\${n} бот остановлен  \${d}→ avito start\${n}"
  fi
  local last=\$(grep -a "INFO \[" "$DIR/avito.log" 2>/dev/null | tail -n 1)
  [ -n "\$last" ] && echo -e "  \${d}\${last:0:60}\${n}"
  echo -e "  \${d}avito logs · status · stop · start · theme\${n}"
  echo
}
avito_banner
PS1='\[\e[38;5;117m\]❯\[\e[0m\] '
# <<< avito-banner <<<
EOF

termux-reload-settings 2>/dev/null || true
echo "Готово: тема «$THEME». Перезапустите Termux (или откройте новую сессию), чтобы увидеть приветствие."
