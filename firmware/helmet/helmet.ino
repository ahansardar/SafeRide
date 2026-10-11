/*
  SafeRide - helmet unit
  Sends a compact safety packet to the desktop app over USB or HC-05 serial.
*/

#include <SoftwareSerial.h>

const uint8_t ALCOHOL_PIN = A0;
const uint8_t HELMET_IR_PIN = 2;
const uint8_t EYE_IR_PIN = 3;
const uint8_t LED_PIN = 7;
const uint8_t BUZZER_PIN = 8;
const uint8_t BLUETOOTH_RX_PIN = 10;
const uint8_t BLUETOOTH_TX_PIN = 11;

const int ALCOHOL_THRESHOLD = 400;
const unsigned long DROWSY_LIMIT_MS = 3000;
const unsigned long SEND_INTERVAL_MS = 250;
const bool HELMET_ACTIVE_LOW = true;
const bool EYE_ACTIVE_LOW = true;
const bool BLUETOOTH_MODE = false;

SoftwareSerial bluetoothSerial(BLUETOOTH_RX_PIN, BLUETOOTH_TX_PIN);
Stream *telemetryPort = &Serial;

unsigned long eyeClosedSince = 0;
unsigned long lastSendAt = 0;
bool eyeTimerActive = false;

void setup() {
  pinMode(ALCOHOL_PIN, INPUT);
  pinMode(HELMET_IR_PIN, HELMET_ACTIVE_LOW ? INPUT_PULLUP : INPUT);
  pinMode(EYE_IR_PIN, EYE_ACTIVE_LOW ? INPUT_PULLUP : INPUT);
  pinMode(LED_PIN, OUTPUT);
  pinMode(BUZZER_PIN, OUTPUT);

  digitalWrite(LED_PIN, LOW);
  digitalWrite(BUZZER_PIN, LOW);
  Serial.begin(9600);
  if (BLUETOOTH_MODE) {
    bluetoothSerial.begin(9600);
    telemetryPort = &bluetoothSerial;
  }
  telemetryPort->print("DEVICE:HELMET,FIRMWARE:3.0,TRANSPORT:");
  telemetryPort->println(BLUETOOTH_MODE ? "BLUETOOTH" : "USB_BRIDGE");
}

void loop() {
  const int alcoholValue = analogRead(ALCOHOL_PIN);
  const bool helmetWorn = digitalRead(HELMET_IR_PIN) == (HELMET_ACTIVE_LOW ? LOW : HIGH);
  const bool eyeClosed = digitalRead(EYE_IR_PIN) == (EYE_ACTIVE_LOW ? LOW : HIGH);
  bool drowsy = false;

  if (eyeClosed) {
    if (!eyeTimerActive) {
      eyeClosedSince = millis();
      eyeTimerActive = true;
    }
    drowsy = millis() - eyeClosedSince >= DROWSY_LIMIT_MS;
  } else {
    eyeTimerActive = false;
  }

  const bool alcoholDetected = alcoholValue > ALCOHOL_THRESHOLD;
  const bool danger = !helmetWorn || alcoholDetected || drowsy;
  digitalWrite(LED_PIN, danger ? HIGH : LOW);

  // A non-blocking warning pulse keeps telemetry smooth.
  const unsigned long pulse = drowsy ? 120 : (alcoholDetected ? 220 : 600);
  digitalWrite(BUZZER_PIN, danger && (millis() % pulse < pulse / 2) ? HIGH : LOW);

  if (millis() - lastSendAt >= SEND_INTERVAL_MS) {
    lastSendAt = millis();
    telemetryPort->print("H:"); telemetryPort->print(helmetWorn ? 1 : 0);
    telemetryPort->print(",A:"); telemetryPort->print(alcoholDetected ? 1 : 0);
    telemetryPort->print(",D:"); telemetryPort->print(drowsy ? 1 : 0);
    telemetryPort->print(",M:"); telemetryPort->println(alcoholValue);
  }
}

