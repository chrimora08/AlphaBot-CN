import RPi.GPIO as GPIO


class AlphaBot:

    # Modalita' di velocita' (% di PWM)
    MODALITA = {
        "lenta": 20,
        "normale": 50,
        "veloce": 90,
    }

    # In curva (left/right) la velocita' non supera quella di "normale"
    VELOCITA_MAX_CURVA = MODALITA["normale"]

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
        self.pwm_a.start(self._speed)
        self.pwm_b.start(self._speed)

        self.stop()

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

    def backward(self):
        self._curva = False
        self._aggiorna_pwm()
        GPIO.output(self.IN1, GPIO.LOW)
        GPIO.output(self.IN2, GPIO.HIGH)
        GPIO.output(self.IN3, GPIO.HIGH)
        GPIO.output(self.IN4, GPIO.LOW)

    def forward(self):
        self._curva = False
        self._aggiorna_pwm()
        GPIO.output(self.IN1, GPIO.HIGH)
        GPIO.output(self.IN2, GPIO.LOW)
        GPIO.output(self.IN3, GPIO.LOW)
        GPIO.output(self.IN4, GPIO.HIGH)

    def right(self):
        self._curva = True
        self._aggiorna_pwm()
        GPIO.output(self.IN1, GPIO.HIGH)
        GPIO.output(self.IN2, GPIO.LOW)
        GPIO.output(self.IN3, GPIO.HIGH)
        GPIO.output(self.IN4, GPIO.LOW)

    def left(self):
        self._curva = True
        self._aggiorna_pwm()
        GPIO.output(self.IN1, GPIO.LOW)
        GPIO.output(self.IN2, GPIO.HIGH)
        GPIO.output(self.IN3, GPIO.LOW)
        GPIO.output(self.IN4, GPIO.HIGH)

    def stop(self):
        self._curva = False
        GPIO.output(self.IN1, GPIO.LOW)
        GPIO.output(self.IN2, GPIO.LOW)
        GPIO.output(self.IN3, GPIO.LOW)
        GPIO.output(self.IN4, GPIO.LOW)

    def cleanup(self):
        self.stop()
        self.pwm_a.stop()
        self.pwm_b.stop()
        GPIO.cleanup()