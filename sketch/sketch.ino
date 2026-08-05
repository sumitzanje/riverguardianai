/*
 * Project: RiverGuardian AI
 * Module 1: Sensor Node - Hardware Acceptance Test v1.6
 * Purpose: Read DYP-A16NY4W RS485 ultrasonic water-level sensor
 * Protocol: Modbus RTU over RS485, 9600-8-N-1
 *
 * Output format:
 * JSON line over Serial
 */

#include <Arduino.h>
#include <math.h>

#define NODE_ID "UB-01"

#define RS485_CONTROL_PIN 2
#define MODBUS_BAUD 9600
#define PC_SERIAL_BAUD 115200

#define SAMPLE_INTERVAL_MS 3000
#define MICRO_SAMPLE_COUNT 3
#define RESPONSE_TIMEOUT_MS 150
#define MICRO_SAMPLE_DELAY_MS 50

// Sensor profile switch:
// 0 = production-safe filtering (default)
// 1 = bench-test responsiveness for close-hand tests and quick rebound checks
#define BENCH_TEST_MODE 0

// The DYP-A16NY4W is reliable in the near-field flood-monitoring zone, but the
// bridge deployment still needs a physical plausibility gate for bad echoes.
// Datasheet: Measurement range 50 cm to 1500 cm, blind zone ≈ 50 cm.
#define MIN_PLAUSIBLE_DISTANCE_CM 50.0
#define MAX_PLAUSIBLE_DISTANCE_CM 1500.0
// Nikhop is a river confluence (Ulhas + Poshir). Peak monsoon waves at ~1 Hz
// with 10-15 cm amplitude can move the surface ~10-12 cm in the 150ms sample
// window. 15 cm covers real turbulence + 3 cm margin while still rejecting
// corrupted RS485 readings in the critical 2-sample (1 Modbus failure) case.
#define MAX_MICRO_SAMPLE_SPREAD_CM 15.0

#if BENCH_TEST_MODE
// Bench profile: accept large rebound changes quickly when hand/object is removed.
#define MAX_STEP_CHANGE_CM 200.0
#define JUMP_CONFIRM_TOLERANCE_CM 30.0
#define JUMP_CONFIRM_REQUIRED_CYCLES 1
#else
// Production profile:
// Raigad extreme cloudburst: ~8 cm/min rise = 0.4 cm per 3-sec cycle.
// Flash surge at confluence peak: ~20 cm/min = 1 cm per 3-sec cycle.
// 20 cm step-gate gives 20x headroom over worst-case real flood rise.
#define MAX_STEP_CHANGE_CM 20.0
#define JUMP_CONFIRM_TOLERANCE_CM 10.0
#define JUMP_CONFIRM_REQUIRED_CYCLES 3
#endif

// DYP Modbus request: device address 0x01, function 0x03
const byte modbusRequest[] = {
  0x01, 0x03, 0x01, 0x01, 0x00, 0x01, 0xD4, 0x36
};

unsigned long lastExecutionTime = 0;
unsigned long packetSequence = 0;
float lastAcceptedDistanceCm = -1.0;
float pendingJumpDistanceCm = -1.0;
float lastRawDistanceCm = -1.0;
bool pendingJumpActive = false;
unsigned int jumpConfirmCount = 0;  // Track consecutive readings at jumped level

uint16_t modbusCrc16(const byte* data, int length);
float maxSample(float values[], int count);
float minSample(float values[], int count);
const char* validateDistance(float filteredDistance, float readings[], int count);
void printOkPacket(float distanceCm, float rawDistanceCm, int validSamples, int failedSamples);
void printErrorPacket(const char* errorCode, float rawDistanceCm, int validSamples, int failedSamples);

void setup() {
  Serial.begin(PC_SERIAL_BAUD);
  Serial1.begin(MODBUS_BAUD);

  pinMode(RS485_CONTROL_PIN, OUTPUT);
  digitalWrite(RS485_CONTROL_PIN, LOW);

  delay(500);

  Serial.print("{\"node_id\":\"UB-01\",\"event\":\"BOOT\",\"status\":\"READY\",\"fw_profile\":\"");
#if BENCH_TEST_MODE
  Serial.print("BENCH");
#else
  Serial.print("PROD");
#endif
  Serial.print("\",\"fw_build\":\"");
  Serial.print(__DATE__);
  Serial.print(" ");
  Serial.print(__TIME__);
  Serial.println("\"}");
}

void loop() {
  if (millis() - lastExecutionTime >= SAMPLE_INTERVAL_MS) {
    lastExecutionTime = millis();

    float readings[MICRO_SAMPLE_COUNT] = {0.0, 0.0, 0.0};
    int validSamples = 0;
    int failedSamples = 0;

    for (int sample = 0; sample < MICRO_SAMPLE_COUNT; sample++) {
      float distanceCm = readDistanceCm();

      if (distanceCm > 0.0) {
        readings[validSamples] = distanceCm;
        validSamples++;
      } else {
        failedSamples++;
      }

      delay(MICRO_SAMPLE_DELAY_MS);
    }

    if (validSamples >= 2) {
      float filteredDistance = medianFilter(readings, validSamples);
      const char* validationError = validateDistance(filteredDistance, readings, validSamples);
      lastRawDistanceCm = filteredDistance;

      if (validationError == NULL) {
        printOkPacket(filteredDistance, filteredDistance, validSamples, failedSamples);
      } else {
        printErrorPacket(validationError, filteredDistance, validSamples, failedSamples);
      }
    } else {
      lastRawDistanceCm = -1.0;
      printErrorPacket("E01_SIGNAL_LOSS", -1.0, validSamples, failedSamples);
    }
  }
}

float readDistanceCm() {
  while (Serial1.available() > 0) {
    Serial1.read();
  }

  digitalWrite(RS485_CONTROL_PIN, HIGH);
  delay(5);

  Serial1.write(modbusRequest, sizeof(modbusRequest));
  Serial1.flush();

  digitalWrite(RS485_CONTROL_PIN, LOW);

  unsigned long listenStart = millis();
  byte responseBuffer[7];
  int byteCount = 0;

  while ((millis() - listenStart < RESPONSE_TIMEOUT_MS) && (byteCount < 7)) {
    if (Serial1.available() > 0) {
      responseBuffer[byteCount] = Serial1.read();
      byteCount++;
    }
  }

  if (byteCount != 7) {
    return -1.0;
  }

  if (responseBuffer[0] != 0x01 || responseBuffer[1] != 0x03) {
    return -1.0;
  }

  uint16_t expectedCrc = static_cast<uint16_t>(responseBuffer[5]) |
                         (static_cast<uint16_t>(responseBuffer[6]) << 8);
  uint16_t actualCrc = modbusCrc16(responseBuffer, 5);
  if (expectedCrc != actualCrc) {
    return -1.0;
  }

  int rawMm = (responseBuffer[3] << 8) | responseBuffer[4];

  if (rawMm <= 0) {
    return -1.0;
  }

  float distanceCm = rawMm / 10.0;

  return distanceCm;
}

uint16_t modbusCrc16(const byte* data, int length) {
  uint16_t crc = 0xFFFF;

  for (int i = 0; i < length; i++) {
    crc ^= static_cast<uint16_t>(data[i]);
    for (int bit = 0; bit < 8; bit++) {
      if ((crc & 0x0001U) != 0U) {
        crc = static_cast<uint16_t>((crc >> 1) ^ 0xA001U);
      } else {
        crc = static_cast<uint16_t>(crc >> 1);
      }
    }
  }

  return crc;
}

float medianFilter(float values[], int count) {
  float temp[3];

  for (int i = 0; i < count; i++) {
    temp[i] = values[i];
  }

  for (int i = 0; i < count - 1; i++) {
    for (int j = i + 1; j < count; j++) {
      if (temp[i] > temp[j]) {
        float swapVal = temp[i];
        temp[i] = temp[j];
        temp[j] = swapVal;
      }
    }
  }

  if (count == 2) {
    return (temp[0] + temp[1]) / 2.0;
  }

  return temp[count / 2];
}

float maxSample(float values[], int count) {
  float maxValue = values[0];

  for (int i = 1; i < count; i++) {
    if (values[i] > maxValue) {
      maxValue = values[i];
    }
  }

  return maxValue;
}

float minSample(float values[], int count) {
  float minValue = values[0];

  for (int i = 1; i < count; i++) {
    if (values[i] < minValue) {
      minValue = values[i];
    }
  }

  return minValue;
}

const char* validateDistance(float filteredDistance, float readings[], int count) {
  float spreadCm = maxSample(readings, count) - minSample(readings, count);

  if (spreadCm > MAX_MICRO_SAMPLE_SPREAD_CM) {
    pendingJumpActive = false;
    jumpConfirmCount = 0;
    return "E02_NOISY_SAMPLES";
  }

  if (filteredDistance < MIN_PLAUSIBLE_DISTANCE_CM || filteredDistance > MAX_PLAUSIBLE_DISTANCE_CM) {
    pendingJumpActive = false;
    jumpConfirmCount = 0;
    return "E03_OUT_OF_RANGE";
  }

  if (lastAcceptedDistanceCm < 0.0) {
    lastAcceptedDistanceCm = filteredDistance;
    pendingJumpDistanceCm = filteredDistance;
    pendingJumpActive = false;
    jumpConfirmCount = 0;
    return NULL;
  }

  float deltaCm = fabs(filteredDistance - lastAcceptedDistanceCm);

  // Normal change within step threshold: accept immediately.
  if (deltaCm <= MAX_STEP_CHANGE_CM) {
    lastAcceptedDistanceCm = filteredDistance;
    pendingJumpDistanceCm = filteredDistance;
    pendingJumpActive = false;
    jumpConfirmCount = 0;
    return NULL;
  }

  // Big jump: require repeated confirmation at the new level before accepting it.
  if (pendingJumpActive && fabs(filteredDistance - pendingJumpDistanceCm) <= JUMP_CONFIRM_TOLERANCE_CM) {
    jumpConfirmCount++;

    if (jumpConfirmCount >= JUMP_CONFIRM_REQUIRED_CYCLES) {
      lastAcceptedDistanceCm = filteredDistance;
      pendingJumpDistanceCm = filteredDistance;
      pendingJumpActive = false;
      jumpConfirmCount = 0;
      return NULL;
    }

    return "E04_UNCONFIRMED_JUMP";
  }

  pendingJumpDistanceCm = filteredDistance;
  pendingJumpActive = true;
  jumpConfirmCount = 1;

  if (jumpConfirmCount >= JUMP_CONFIRM_REQUIRED_CYCLES) {
    lastAcceptedDistanceCm = filteredDistance;
    pendingJumpActive = false;
    jumpConfirmCount = 0;
    return NULL;
  }

  return "E04_UNCONFIRMED_JUMP";
}

void printOkPacket(float distanceCm, float rawDistanceCm, int validSamples, int failedSamples) {
  packetSequence++;

  Serial.print("{");
  Serial.print("\"node_id\":\"");
  Serial.print(NODE_ID);
  Serial.print("\",");

  Serial.print("\"fw_profile\":\"");
#if BENCH_TEST_MODE
  Serial.print("BENCH");
#else
  Serial.print("PROD");
#endif
  Serial.print("\",");

  Serial.print("\"fw_build\":\"");
  Serial.print(__DATE__);
  Serial.print(" ");
  Serial.print(__TIME__);
  Serial.print("\",");

  Serial.print("\"packet_sequence\":");
  Serial.print(packetSequence);
  Serial.print(",");

  Serial.print("\"measurement_state\":\"OK\",");

  Serial.print("\"uptime_ms\":");
  Serial.print(millis());
  Serial.print(",");

  Serial.print("\"distance_cm\":");
  Serial.print(distanceCm, 1);
  Serial.print(",");

  Serial.print("\"raw_distance_cm\":");
  Serial.print(rawDistanceCm, 1);
  Serial.print(",");

  Serial.print("\"accepted_distance_cm\":");
  Serial.print(lastAcceptedDistanceCm, 1);
  Serial.print(",");

  Serial.print("\"candidate_distance_cm\":");
  Serial.print(distanceCm, 1);
  Serial.print(",");

  Serial.print("\"valid_samples\":");
  Serial.print(validSamples);
  Serial.print(",");

  Serial.print("\"failed_samples\":");
  Serial.print(failedSamples);
  Serial.print(",");

  Serial.print("\"sensor_status\":\"OK\"");
  Serial.println("}");
}

void printErrorPacket(const char* errorCode, float rawDistanceCm, int validSamples, int failedSamples) {
  packetSequence++;

  Serial.print("{");
  Serial.print("\"node_id\":\"");
  Serial.print(NODE_ID);
  Serial.print("\",");

  Serial.print("\"fw_profile\":\"");
#if BENCH_TEST_MODE
  Serial.print("BENCH");
#else
  Serial.print("PROD");
#endif
  Serial.print("\",");

  Serial.print("\"fw_build\":\"");
  Serial.print(__DATE__);
  Serial.print(" ");
  Serial.print(__TIME__);
  Serial.print("\",");

  Serial.print("\"packet_sequence\":");
  Serial.print(packetSequence);
  Serial.print(",");

  Serial.print("\"measurement_state\":\"");
  Serial.print(errorCode);
  Serial.print("\",");

  Serial.print("\"uptime_ms\":");
  Serial.print(millis());
  Serial.print(",");

  if (rawDistanceCm >= 0.0) {
    Serial.print("\"raw_distance_cm\":");
    Serial.print(rawDistanceCm, 1);
    Serial.print(",");

    Serial.print("\"candidate_distance_cm\":");
    Serial.print(rawDistanceCm, 1);
    Serial.print(",");
  }

  if (lastAcceptedDistanceCm >= 0.0) {
    Serial.print("\"accepted_distance_cm\":");
    Serial.print(lastAcceptedDistanceCm, 1);
    Serial.print(",");
  }

  Serial.print("\"error\":\"");
  Serial.print(errorCode);
  Serial.print("\",");

  Serial.print("\"valid_samples\":");
  Serial.print(validSamples);
  Serial.print(",");

  Serial.print("\"failed_samples\":");
  Serial.print(failedSamples);
  Serial.print(",");

  Serial.print("\"sensor_status\":\"FAULT\"");
  Serial.println("}");
}