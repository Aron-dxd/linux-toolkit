//.config/proxy/tor.pac
//Use TOR proxy if available, otherwise fallback to direct connection
//Add as file path in browser under automatic proxy configuration URL

function FindProxyForURL(url, host) {
    // If Tor SOCKS proxy is available, use it
    // Otherwise, fall back to direct connection
    return "SOCKS5 127.0.0.1:9050; DIRECT";
}
