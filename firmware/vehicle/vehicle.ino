/*
  SafeRide - vehicle unit
  Receives real helmet packets from the desktop bridge over USB or HC-05 serial.
*/

const uint8_t RELAY_PIN = 4;
const uint8_t LED_PIN = 5;
const uint8_t BUZZER_PIN = 6;
const unsigned long LINK_TIMEOUT_MS = 2000;
const unsigned long SEND_INTERVAL_MS = 250;
const bool RELAY_ACTIVE_HIGH = true;
const bool BLUETOOTH_MODE = false;

String inputLine;
int helmetStatus = 0;
int alcoholStatus = 0;
int drowsyStatus = 0;
int alcoholValue = 0;
unsigned long lastPacketAt = 0;
unsigned long lastSendAt = 0;

int readField(const String &line, const String &key) {
  int start = line.indexOf(key);
  if (start < 0) return -1;
  start += key.length();
  int finish = line.indexOf(',', start);
  if (finish < 0) finish = line.length();
  return line.substring(start, finish).toInt();
}

void acceptPacket(String line) {
  line.trim();
  const int h = readField(line, "H:");
  const int a = readField(line, "A:");
  const int d = readField(line, "D:");
  const int m = readField(line, "M:");
  if (h >= 0 && a >= 0 && d >= 0 && m >= 0) {
    helmetStatus = h;
    alcoholStatus = a;
    drowsyStatus = d;
    alcoholValue = m;
    lastPacketAt = millis();
  }
}

void setup() {
  pinMode(RELAY_PIN, OUTPUT);
  pinMode(LED_PIN, OUTPUT);
  pinMode(BUZZER_PIN, OUTPUT);
  digitalWrite(RELAY_PIN, RELAY_ACTIVE_HIGH ? LOW : HIGH);
  Serial.begin(9600);
  Serial.print("DEVICE:VEHICLE,FIRMWARE:3.1,TRANSPORT:");
  Serial.println(BLUETOOTH_MODE ? "BLUETOOTH" : "USB_BRIDGE");
}

void loop() {
  while (Serial.available()) {
    const char incoming = Serial.read();
    if (incoming == '\n') {
      acceptPacket(inputLine);
      inputLine = "";
    } else if (incoming != '\r' && inputLine.length() < 96) {
      inputLine += incoming;
    }
  }

  const bool linkAlive = lastPacketAt > 0 && millis() - lastPacketAt <= LINK_TIMEOUT_MS;
  const bool rideAllowed = linkAlive && helmetStatus == 1 && alcoholStatus == 0 && drowsyStatus == 0;
  digitalWrite(RELAY_PIN, rideAllowed == RELAY_ACTIVE_HIGH ? HIGH : LOW);
  digitalWrite(LED_PIN, rideAllowed ? LOW : HIGH);

  const bool danger = linkAlive && (helmetStatus == 0 || alcoholStatus == 1 || drowsyStatus == 1);
  const unsigned long pulse = drowsyStatus ? 120 : (alcoholStatus ? 220 : 600);
  digitalWrite(BUZZER_PIN, danger && (millis() % pulse < pulse / 2) ? HIGH : LOW);

  if (millis() - lastSendAt >= SEND_INTERVAL_MS) {
    lastSendAt = millis();
    Serial.print("H:"); Serial.print(helmetStatus);
    Serial.print(",A:"); Serial.print(alcoholStatus);
    Serial.print(",D:"); Serial.print(drowsyStatus);
    Serial.print(",M:"); Serial.print(alcoholValue);
    Serial.print(",ENGINE:"); Serial.print(rideAllowed ? 1 : 0);
    Serial.print(",LINK:"); Serial.println(linkAlive ? 1 : 0);
  }
}

