import time
from wasd.libreria import AlphaBot

# --- Parametri da calibrare ---
VELOCITA = 50            # 0-100
TEMPO_AVANTI = 2.0       # secondi di marcia in avanti
TEMPO_MEZZOGIRO = 0.9    # secondi per ruotare di 180° (da tarare sul tuo robot)
PAUSA = 0.5              # pausa tra un movimento e l'altro (fa assestare il robot)


def main():
    robot = AlphaBot(speed=VELOCITA)

    try:
        # 1. Vai avanti
        robot.forward()
        time.sleep(TEMPO_AVANTI)
        robot.stop()
        time.sleep(PAUSA)

        # 2. Mezzo giro sul posto (180°)
        robot.right()
        time.sleep(TEMPO_MEZZOGIRO)
        robot.stop()
        time.sleep(PAUSA)

        # 3. Torna al punto di partenza (stesso tempo dell'andata)
        robot.forward()
        time.sleep(TEMPO_AVANTI)
        robot.stop()

    except KeyboardInterrupt:
        pass  # Ctrl+C per fermarlo in qualsiasi momento
    finally:
        robot.cleanup()


if __name__ == "__main__":
    main()