#!/bin/bash
set -euo pipefail

GREEN="\033[1;32m"
RESET="\033[0m"

sudo -v

echo -e "${GREEN}CLEARING UP SOME TRASH FOR YOU, MASTER..${RESET}"
echo -e "${GREEN}-----------------------------------------${RESET}"

echo -e "${GREEN}Synchronizing reality itself...${RESET}"
sudo pacman -Syu --noconfirm
echo -e "${GREEN}-----------------------------------------${RESET}"

echo -e "${GREEN}Hunting orphaned packages...${RESET}"
orphans=$(pacman -Qtdq || true)
if [ -n "$orphans" ]; then
    sudo pacman -Rns $orphans --noconfirm
else
    echo -e "${GREEN}No souls left to claim.${RESET}"
fi
echo -e "${GREEN}-----------------------------------------${RESET}"

if command -v yay &>/dev/null; then
    echo -e "${GREEN}Purging AUR remnants...${RESET}"
    yay -Sc --noconfirm
    echo -e "${GREEN}-----------------------------------------${RESET}"
fi

echo -e "${GREEN}Trimming pacman cache...${RESET}"
sudo paccache -r -k 2
echo -e "${GREEN}-----------------------------------------${RESET}"

echo -e "${GREEN}Let systemd handle the filth...${RESET}"
sudo systemd-tmpfiles --clean
echo -e "${GREEN}-----------------------------------------${RESET}"

[ -d "$HOME/.cache/thumbnails" ] && rm -rf "$HOME/.cache/thumbnails"/*
echo -e "${GREEN}-----------------------------------------${RESET}"

if command -v flatpak &>/dev/null; then
    echo -e "${GREEN}Erasing unused Flatpak baggage...${RESET}"
    flatpak remove --unused -y
    echo -e "${GREEN}-----------------------------------------${RESET}"
fi

echo -e "${GREEN}Sealing ancient system sins...${RESET}"
sudo journalctl --vacuum-time=7d
echo -e "${GREEN}-----------------------------------------${RESET}"

echo -e "${GREEN}Cleanup complete. The machine purrs.${RESET}"
