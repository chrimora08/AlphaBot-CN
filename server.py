import socket
import threading

from libreria import AlphaBot

# --- Parametri ---
HOST = "0.0.0.0"      # ascolta su tutte le interfacce della Raspberry
PORT = 5000
TIMEOUT = 1.0         # secondi senza messaggi (nemmeno PING) -> il robot si ferma
STEP_VELOCITA = 10


def applica(robot, premuti):
    """Muove il robot in base all'ultimo tasto ancora premuto."""
    if not premuti:
        robot.stop()
        return

    azioni = {
        "w": robot.forward,
        "s": robot.backward,
        "a": robot.left,
        "d": robot.right,
    }
    azioni[premuti[-1]]()


def gestisci_client(conn, robot):
    conn.settimeout(TIMEOUT)
    premuti = []      # tasti attualmente premuti, in ordine di pressione
    buffer = ""

    while True:
        try:
            dati = conn.recv(1024)
        except socket.timeout:
            # Nessun segnale dal client: per sicurezza ferma il robot
            premuti.clear()
            robot.stop()
            continue
        except ConnectionError:
            break

        if not dati:      # il client ha chiuso la connessione
            break

        buffer += dati.decode(errors="ignore")

        while "\n" in buffer:
            riga, buffer = buffer.split("\n", 1)
            parti = riga.strip().split()
            if not parti:
                continue

            comando = parti[0].upper()
            arg = parti[1].lower() if len(parti) > 1 else ""

            if comando == "DOWN" and arg in ("w", "a", "s", "d"):
                if arg in premuti:
                    premuti.remove(arg)
                premuti.append(arg)
                applica(robot, premuti)

            elif comando == "UP" and arg in premuti:
                premuti.remove(arg)
                applica(robot, premuti)

            elif comando == "MODE":
                # Modalita' assoluta: "lenta", "normale" o "veloce"
                if arg in AlphaBot.MODALITA:
                    robot.set_mode(arg)
                    print(f"Modalita': {arg} ({robot.speed}%)")

            elif comando == "SPEED":
                # Compatibilita' con il vecchio client_wasd.py
                if arg == "+":
                    robot.increase_speed(STEP_VELOCITA)
                elif arg == "-":
                    robot.decrease_speed(STEP_VELOCITA)
                print(f"Velocita': {robot.speed}%")

            # PING: serve solo a tenere vivo il timeout, non fa nulla

    premuti.clear()
    robot.stop()


def main():
    robot = AlphaBot()

    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind((HOST, PORT))
    server.listen(1)
    print(f"In ascolto sulla porta {PORT}... (Ctrl+C per uscire)")

    try:
        while True:
            conn, indirizzo = server.accept()
            conn.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            print(f"Client connesso: {indirizzo[0]}")
            robot.set_mode("normale")   # ogni nuova connessione riparte da "normale"

            # Avvisa il client quando scatta lo stop per ostacolo / via libera.
            # Viene chiamata anche dal thread dei sensori, quindi serve un lock.
            lock_invio = threading.Lock()

            def segnala(messaggio, conn=conn, lock_invio=lock_invio):
                print(f"Evento: {messaggio}")
                try:
                    with lock_invio:
                        conn.sendall((messaggio + "\n").encode())
                except OSError:
                    pass

            robot.on_evento = segnala
            try:
                gestisci_client(conn, robot)
            finally:
                robot.on_evento = None
                robot.stop()
                conn.close()
                print("Client disconnesso, robot fermo.")
    except KeyboardInterrupt:
        print("\nChiusura...")
    finally:
        server.close()
        robot.cleanup()


if __name__ == "__main__":
    main()