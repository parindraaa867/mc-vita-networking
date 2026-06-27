#!/usr/bin/env python3
"""
Minecraft Vita custom-server — PC side (foundation).

Role: always-on coordinator + canonical world store + relay. It does NOT run the
game; a Vita (the first to connect) hosts the world. This program:
  - accepts mod connections from Vitas (the plugin connects here)
  - assigns the first connection as HOST, the rest as JOINERS
  - (next) serves the stored world save to the host and takes it back
  - (next) relays game data between host and joiners

This foundation handles the hello handshake + host/join role assignment + a
world-save store on disk, so you can confirm the Vita reaches it. The relay and
world-transfer wire format are stubbed with clear TODOs to match the plugin.
"""
import socket
import threading
import os

HOST = "0.0.0.0"
PORT = 25700
WORLD_DIR = os.path.join(os.path.dirname(__file__), "worlds")
os.makedirs(WORLD_DIR, exist_ok=True)

_lock = threading.Lock()
_clients = []          # list of dicts: {sock, addr, role}
_host_client = None    # the current host connection


def assign_role(client):
    global _host_client
    with _lock:
        if _host_client is None:
            _host_client = client
            client["role"] = "HOST"
        else:
            client["role"] = "JOIN"
    return client["role"]


def handle(sock, addr):
    client = {"sock": sock, "addr": addr, "role": None}
    with _lock:
        _clients.append(client)
    print(f"[+] connection from {addr[0]}:{addr[1]} ({len(_clients)} total)")
    try:
        hello = sock.recv(256)
        if not hello:
            return
        print(f"    hello: {hello!r}")
        role = assign_role(client)
        print(f"    -> assigned role: {role}")

        # Tell the mod its role. The plugin will branch on this:
        #   HOST -> request the world save, load it, host
        #   JOIN -> ask to be relayed to the host
        sock.sendall(f"ROLE {role}\n".encode())

        # TODO (next milestones), matching the plugin's protocol:
        #  - if HOST: send the stored world blob (worlds/current.bin) or NEW if none;
        #             receive periodic save uploads -> write to worlds/current.bin
        #  - if JOIN: bridge this socket <-> host socket (relay game data)
        # For now, keep the connection alive and log anything received.
        while True:
            data = sock.recv(4096)
            if not data:
                break
            print(f"    [{role}] {len(data)}B: {data[:48]!r}")
    except Exception as e:
        print(f"    error {addr}: {e}")
    finally:
        global _host_client
        with _lock:
            if client in _clients:
                _clients.remove(client)
            if _host_client is client:
                _host_client = None
                print("[!] host left — world session ended (save should be on disk)")
        sock.close()
        print(f"[-] {addr[0]} disconnected")


def main():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind((HOST, PORT))
    s.listen(8)
    print(f"Minecraft Vita PC server listening on {HOST}:{PORT}")
    print(f"World store: {WORLD_DIR}")
    print("Waiting for modded Vitas to connect...\n")
    while True:
        conn, addr = s.accept()
        threading.Thread(target=handle, args=(conn, addr), daemon=True).start()


if __name__ == "__main__":
    main()
