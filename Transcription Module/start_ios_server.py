#!/usr/bin/env python3
"""
iPhone Local Server Launcher
Automatically discovers local Wi-Fi IP and serves the offline PWA transcriber.
Allows you to scan a QR code from your iPhone camera to instantly load and install the app.
"""

import os
import sys
import socket
import http.server
import socketserver

def get_local_ip():
    """Finds the primary local network IP of this machine."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        # Does not actually make an external connection, just queries local routing table
        s.connect(('10.255.255.255', 1))
        ip = s.getsockname()[0]
    except Exception:
        ip = '127.0.0.1'
    finally:
        s.close()
    return ip

def print_qr(url):
    """Attempts to display a terminal QR code if qrcode is installed."""
    try:
        import qrcode
        qr = qrcode.QRCode(border=1)
        qr.add_data(url)
        qr.make(fit=True)
        print("\n" + "=" * 50)
        print(" SCAN THIS QR CODE WITH YOUR IPHONE CAMERA:")
        print("=" * 50)
        qr.print_ascii(invert=True)
    except ImportError:
        print("\n" + "=" * 50)
        print(" (Tip: Run 'pip install qrcode' to see a scannable QR code right here)")
        print("=" * 50)

def main():
    port = 8080
    host_ip = get_local_ip()
    
    # Target directory is the Transcription Module
    script_dir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(script_dir)
    
    url = f"http://{host_ip}:{port}/ios/pwa_offline_transcriber.html"
    
    print("\n" + "#" * 60)
    print("  OFFLINE TRANSCRIBER - IPHONE LOCAL SERVER LAUNCHER")
    print("#" * 60)
    print(f"\n • Local Server Running On: {url}")
    print(" • Steps for your iPhone:")
    print("   1. Ensure your iPhone is on the same Wi-Fi network.")
    print(f"   2. Open Safari and navigate to:\n      {url}")
    print("   3. Tap the 'Share' icon (square with arrow pointing up).")
    print("   4. Tap 'Add to Home Screen'.")
    print("   5. Done! The app is now installed on your iPhone.")
    
    print_qr(url)
    
    Handler = http.server.SimpleHTTPRequestHandler
    
    # Allow port reuse immediately
    socketserver.TCPServer.allow_reuse_address = True
    
    try:
        with socketserver.TCPServer(("0.0.0.0", port), Handler) as httpd:
            print(f"\n[Server] Listening on port {port}... Press Ctrl+C to stop.")
            httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n[Server] Shutting down.")
        sys.exit(0)

if __name__ == "__main__":
    main()
