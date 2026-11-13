import socket
import sys
import threading
import time

from pynput import keyboard   # pip install pynput

# --- Parametri ---
PORT = 5000
INTERVALLO_PING = 0.3   # secondi tra un PING e l'altro

TASTI_MOVIMENTO = {"w", "a", "s", "d"}


def main():
    if len(sys.argv) > 1:
        ip = sys.argv[1]
    else:
        ip = input("IP della Raspberry: ").strip()

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
    sock.connect((ip, PORT))
    print("Connesso!")
    print("Tieni premuto W/A/S/D per muoverti | + / - velocita' | ESC per uscire")

    lock = threading.Lock()
    premuti = set()          # serve a ignorare l'auto-repeat della tastiera
    attivo = threading.Event()
    attivo.set()

    def invia(messaggio):
        try:
            with lock:
                sock.sendall((messaggio + "\n").encode())
        except OSError:
            attivo.clear()

    def heartbeat():
        while attivo.is_set():
            invia("PING")
            time.sleep(INTERVALLO_PING)

    threading.Thread(target=heartbeat, daemon=True).start()

    def carattere(tasto):
        c = getattr(tasto, "char", None)
        return c.lower() if c else None

    def on_press(tasto):
        if tasto == keyboard.Key.esc:
            attivo.clear()
            return False

        c = carattere(tasto)
        if c in TASTI_MOVIMENTO:
            if c not in premuti:        # ignora la ripetizione automatica
                premuti.add(c)
                invia(f"DOWN {c}")
        elif c in ("+", "="):
            invia("SPEED +")
        elif c in ("-", "_"):
            invia("SPEED -")

    def on_release(tasto):
        c = carattere(tasto)
        if c in TASTI_MOVIMENTO and c in premuti:
            premuti.discard(c)
            invia(f"UP {c}")

    listener = keyboard.Listener(on_press=on_press, on_release=on_release)
    listener.start()

    try:
        while attivo.is_set() and listener.is_alive():
            time.sleep(0.1)
    except KeyboardInterrupt:
        pass
    finally:
        for c in list(premuti):
            invia(f"UP {c}")
        listener.stop()
        sock.close()
        print("Disconnesso.")


if __name__ == "__main__":
    main()

