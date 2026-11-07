import threading

import RPi.GPIO as GPIO


class AlphaBot:

    # Modalita' di velocita' (% di PWM)
    MODALITA = {
        "lenta": 30,
        "normale": 50,
        "veloce": 80,
    }

    # In curva (left/right) la velocita' non supera quella di "normale"
    VELOCITA_MAX_CURVA = MODALITA["normale"]

    # Sensori di ostacolo
    SENSORE_DX = 16
    SENSORE_SX = 19
    # I sensori IR dell'AlphaBot mettono il pin a LOW quando vedono un ostacolo.
    # Se i tuoi fanno il contrario, metti False.
    SENSORI_ATTIVI_BASSI = True

    # Movimenti bloccati dall'ostacolo (la retromarcia no)
    _BLOCCABILI = ("forward", "left", "right")

    # Uscite (IN1, IN2, IN3, IN4) per ogni movimento
    _H, _L = GPIO.HIGH, GPIO.LOW
    _USCITE = {
        "forward":  (_H, _L, _L, _H),
        "backward": (_L, _H, _H, _L),
        "right":    (_H, _L, _H, _L),
        "left":     (_L, _H, _L, _H),
    }

    def __init__(self, speed=50):
        GPIO.setmode(GPIO.BCM)
        GPIO.setwarnings(False)

        # Pin motori
        self.IN1 = 12
        self.IN2 = 13
        self.IN3 = 20
        self.IN4 = 21

        self.EN_A = 6
        self.EN_B = 26

        GPIO.setup(self.IN1, GPIO.OUT)
        GPIO.setup(self.IN2, GPIO.OUT)
        GPIO.setup(self.IN3, GPIO.OUT)
        GPIO.setup(self.IN4, GPIO.OUT)

        GPIO.setup(self.EN_A, GPIO.OUT)
        GPIO.setup(self.EN_B, GPIO.OUT)

        self.pwm_a = GPIO.PWM(self.EN_A, 1000)
        self.pwm_b = GPIO.PWM(self.EN_B, 1000)

        self._speed = max(0, min(100, speed))
        self._curva = False
        self._bloccabile = False        # True mentre va avanti o gira (bloccabile da ostacolo)
        self._voluto = None             # ultimo movimento richiesto e non ancora rilasciato
        self._segnalato = False         # True se ho gia' avvisato "OSTACOLO"
        self.on_evento = None           # funzione(messaggio) chiamata su OSTACOLO / LIBERO
        self._lock = threading.RLock()  # protegge motori e sensori da accessi simultanei
        self.pwm_a.start(self._speed)
        self.pwm_b.start(self._speed)

        # Sensori: pull-up per avere un livello definito quando non rilevano nulla
        pull = GPIO.PUD_UP if self.SENSORI_ATTIVI_BASSI else GPIO.PUD_DOWN
        for pin in (self.SENSORE_DX, self.SENSORE_SX):
            GPIO.setup(pin, GPIO.IN, pull_up_down=pull)
            # Il callback parte appena il livello del pin cambia
            GPIO.add_event_detect(pin, GPIO.BOTH,
                                  callback=self._on_sensore, bouncetime=5)

        self.stop()

    # --- Sensori ---

    def ostacolo(self):
        """True se almeno uno dei due sensori rileva qualcosa."""
        livello_attivo = GPIO.LOW if self.SENSORI_ATTIVI_BASSI else GPIO.HIGH
        return (GPIO.input(self.SENSORE_DX) == livello_attivo or
                GPIO.input(self.SENSORE_SX) == livello_attivo)

    def _segnala(self, messaggio):
        if self.on_evento:
            try:
                self.on_evento(messaggio)
            except Exception:
                pass    # un problema di rete non deve mai toccare i motori

    def _on_sensore(self, canale):
        """Chiamata dalla libreria GPIO in un thread separato a ogni variazione."""
        messaggio = None
        with self._lock:
            if self.ostacolo():
                # Stop immediato se sta andando avanti o girando
                if self._bloccabile:
                    self._ferma_motori()
                    self._segnalato = True
                    messaggio = "OSTACOLO"
            else:
                # Via libera: se il tasto e' ancora premuto, riparte da solo
                if self._voluto in self._BLOCCABILI and not self._bloccabile:
                    if not self._muovi(self._voluto):
                        messaggio = "OSTACOLO"
                    elif self._segnalato:
                        self._segnalato = False
                        messaggio = "LIBERO"
                elif self._segnalato:
                    self._segnalato = False
                    messaggio = "LIBERO"
        if messaggio:
            self._segnala(messaggio)

    # --- Velocita' ---

    @property
    def speed(self):
        return self._speed

    @speed.setter
    def speed(self, value):
        self._speed = max(0, min(100, value))
        self._aggiorna_pwm()

    def _duty(self):
        """Duty cycle reale: in curva e' limitato a VELOCITA_MAX_CURVA."""
        if self._curva:
            return min(self._speed, self.VELOCITA_MAX_CURVA)
        return self._speed

    def _aggiorna_pwm(self):
        duty = self._duty()
        self.pwm_a.ChangeDutyCycle(duty)
        self.pwm_b.ChangeDutyCycle(duty)

    @property
    def mode(self):
        """Nome della modalita' corrente, o None se la velocita' e' personalizzata."""
        for nome, valore in self.MODALITA.items():
            if valore == self._speed:
                return nome
        return None

    def set_mode(self, nome):
        """Imposta la velocita' da una modalita' ('lenta', 'normale', 'veloce')."""
        if nome not in self.MODALITA:
            raise ValueError(f"Modalita' sconosciuta: {nome}")
        self.speed = self.MODALITA[nome]

    def increase_speed(self, step=10):
        self.speed = self._speed + step

    def decrease_speed(self, step=10):
        self.speed = self._speed - step

    # --- Movimenti ---

    def _scrivi_uscite(self, uscite):
        GPIO.output(self.IN1, uscite[0])
        GPIO.output(self.IN2, uscite[1])
        GPIO.output(self.IN3, uscite[2])
        GPIO.output(self.IN4, uscite[3])

    def _muovi(self, nome):
        """Avvia un movimento (chiamare con il lock preso).
        Restituisce False se l'ostacolo lo impedisce."""
        self._voluto = nome
        bloccabile = nome in self._BLOCCABILI

        if bloccabile and self.ostacolo():
            self._ferma_motori()
            self._segnalato = True
            return False

        self._curva = nome in ("left", "right")
        self._bloccabile = bloccabile
        self._aggiorna_pwm()
        self._scrivi_uscite(self._USCITE[nome])

        # Ricontrollo: se l'ostacolo e' comparso proprio ora, fermati subito
        if bloccabile and self.ostacolo():
            self._ferma_motori()
            self._segnalato = True
            return False
        return True

    def _vai(self, nome):
        with self._lock:
            ok = self._muovi(nome)
        if not ok:
            self._segnala("OSTACOLO")
        return ok

    def backward(self):
        return self._vai("backward")

    def forward(self):
        """Va avanti. Se c'e' un ostacolo resta fermo e restituisce False."""
        return self._vai("forward")

    def right(self):
        return self._vai("right")

    def left(self):
        return self._vai("left")

    def _ferma_motori(self):
        """Ferma i motori ma ricorda cosa stava chiedendo l'utente."""
        self._curva = False
        self._bloccabile = False
        self._scrivi_uscite((GPIO.LOW,) * 4)

    def stop(self):
        """Stop richiesto dall'utente: dimentica anche il movimento voluto."""
        with self._lock:
            self._voluto = None
            self._ferma_motori()

    def cleanup(self):
        self.stop()
        for pin in (self.SENSORE_DX, self.SENSORE_SX):
            GPIO.remove_event_detect(pin)
        self.pwm_a.stop()
        self.pwm_b.stop()
        GPIO.cleanup()