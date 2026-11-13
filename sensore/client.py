import socket
import sys
import threading
import time

from pynput import keyboard   # pip install pynput

# --- Parametri ---
PORT = 5000
INTERVALLO_PING = 0.3   # secondi tra un PING e l'altro

TASTI_MOVIMENTO = {"w", "a", "s", "d"}

# Modalita' di velocita', dalla piu' lenta alla piu' veloce.
# I valori in % sono definiti nella libreria (AlphaBot.MODALITA).
MODALITA = ["lenta", "normale", "veloce"]
INDICE_INIZIALE = 1     # "normale"

# Messaggi inviati dal robot
MESSAGGI_ROBOT = {
    "OSTACOLO": "!!! OSTACOLO rilevato: robot fermo, puoi solo andare indietro (S)",
    "LIBERO": "Via libera: ostacolo rimosso.",
}


def main():
    if len(sys.argv) > 1:
        ip = sys.argv[1]
    else:
        ip = input("IP della Raspberry: ").strip()

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
    sock.connect((ip, PORT))
    print("Connesso!")
    print("Tieni premuto W/A/S/D per muoverti | + piu' veloce | - piu' lento | ESC per uscire")

    lock = threading.Lock()
    premuti = set()          # serve a ignorare l'auto-repeat della tastiera
    attivo = threading.Event()
    attivo.set()

    indice = INDICE_INIZIALE

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

    def imposta_modalita(nuovo_indice):
        """Invia la modalita' in modo ASSOLUTO (non '+1'), cosi' client e
        robot non possono andare fuori sincronia."""
        nonlocal indice
        nuovo_indice = max(0, min(len(MODALITA) - 1, nuovo_indice))
        if nuovo_indice == indice:
            print(f"Modalita' {MODALITA[indice].upper()} (limite raggiunto)")
            return
        indice = nuovo_indice
        invia(f"MODE {MODALITA[indice]}")
        print(f"Modalita': {MODALITA[indice].upper()}")

    # All'avvio forza "normale" anche sul robot
    invia(f"MODE {MODALITA[indice]}")
    print(f"Modalita': {MODALITA[indice].upper()}")

    def ricevi():
        """Riceve i messaggi dal robot (ostacolo / via libera)."""
        buffer = ""
        while attivo.is_set():
            try:
                dati = sock.recv(1024)
            except OSError:
                break
            if not dati:
                if attivo.is_set():
                    print("Connessione chiusa dal robot.")
                attivo.clear()
                break
            buffer += dati.decode(errors="ignore")
            while "\n" in buffer:
                riga, buffer = buffer.split("\n", 1)
                testo = MESSAGGI_ROBOT.get(riga.strip().upper())
                if testo:
                    print(testo)

    threading.Thread(target=heartbeat, daemon=True).start()
    threading.Thread(target=ricevi, daemon=True).start()

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
            if "+" not in premuti:      # un solo cambio per pressione
                premuti.add("+")
                imposta_modalita(indice + 1)
        elif c in ("-", "_"):
            if "-" not in premuti:
                premuti.add("-")
                imposta_modalita(indice - 1)

    def on_release(tasto):
        c = carattere(tasto)
        if c in TASTI_MOVIMENTO and c in premuti:
            premuti.discard(c)
            invia(f"UP {c}")
        elif c in ("+", "="):
            premuti.discard("+")
        elif c in ("-", "_"):
            premuti.discard("-")

    listener = keyboard.Listener(on_press=on_press, on_release=on_release)
    listener.start()

    try:
        while attivo.is_set() and listener.is_alive():
            time.sleep(0.1)
    except KeyboardInterrupt:
        pass
    finally:
        for c in list(premuti):
            if c in TASTI_MOVIMENTO:
                invia(f"UP {c}")
        listener.stop()
        sock.close()
        print("Disconnesso.")


if __name__ == "__main__":
    main()