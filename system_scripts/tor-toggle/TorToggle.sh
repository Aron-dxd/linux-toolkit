# .config/hypr/scripts/TorToggle.sh
#!/bin/bash

TOR_CMD="tor -f $HOME/.tor/torrc"
TOR_PORT=9050

if ss -tulnp | grep -q ":$TOR_PORT"; then
    pkill -f "$TOR_CMD"
    notify-send "Tor" "Tor stopped" -i network-offline
else
    # Tor is not running → start it
    nohup $TOR_CMD > "$HOME/.tor/tor.log" 2>&1 &
    notify-send "Tor" "Tor started (SOCKS5 :9050)" -i network-vpn
fi
