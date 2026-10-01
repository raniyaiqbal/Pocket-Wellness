/*
 * HRV-SHIELD Arduino Sketch
 * ─────────────────────────
 * Reads physiological sensors and sends CSV data to the Flask backend via serial.
 *
 * Expected hardware:
 *   - Pulse sensor (e.g. PulseSensor Playground) on analog pin A0
 *   - Grove GSR (EDA) sensor on analog pin A1
 *   - DS18B20 or LM35 skin temperature sensor on pin A2
 *
 * Output format (1 Hz):
 *   hrv_rmssd,eda_raw,skin_temp_c,heart_rate
 *   e.g.:  42.3,180,36.7,78
 *
 * Install libraries:
 *   PulseSensor Playground  (Sketch → Include Library → Manage Libraries)
 */

// ── pins ──────────────────────────────────────────────────────────
#define PULSE_PIN   A0
#define EDA_PIN     A1
#define TEMP_PIN    A2

// ── HRV computation window ────────────────────────────────────────
const int RR_BUFFER_SIZE = 20;
float  rr_intervals[RR_BUFFER_SIZE];
int    rr_idx     = 0;
bool   rr_full    = false;
unsigned long last_beat_ms = 0;
int    bpm        = 0;

// ── PulseSensor state machine ─────────────────────────────────────
int    pulse_thresh = 512;    // adjust for your sensor
bool   in_beat      = false;

// ── output interval ───────────────────────────────────────────────
unsigned long last_output_ms = 0;
const int OUTPUT_INTERVAL_MS = 1000;   // 1 Hz

void setup() {
  Serial.begin(9600);
  analogReference(DEFAULT);
  Serial.println("HRV-SHIELD sensor ready");
}

void loop() {
  readPulse();

  unsigned long now = millis();
  if (now - last_output_ms >= OUTPUT_INTERVAL_MS) {
    last_output_ms = now;
    emitReading();
  }
}

// ── pulse / HRV reading ───────────────────────────────────────────
void readPulse() {
  int raw = analogRead(PULSE_PIN);
  unsigned long now = millis();

  if (raw > pulse_thresh && !in_beat) {
    in_beat = true;
    if (last_beat_ms > 0) {
      float rr = now - last_beat_ms;         // ms
      if (rr > 300 && rr < 2000) {           // physiologically valid range
        rr_intervals[rr_idx % RR_BUFFER_SIZE] = rr;
        rr_idx++;
        if (rr_idx >= RR_BUFFER_SIZE) rr_full = true;
        bpm = (int)(60000.0 / rr);
      }
    }
    last_beat_ms = now;
  }
  if (raw < pulse_thresh - 20) {
    in_beat = false;
  }
}

// ── RMSSD calculation ─────────────────────────────────────────────
float computeRMSSD() {
  int n = rr_full ? RR_BUFFER_SIZE : rr_idx;
  if (n < 2) return 50.0;  // default before enough data
  float sum_sq = 0;
  for (int i = 1; i < n; i++) {
    int a = (rr_idx - n + i - 1 + RR_BUFFER_SIZE) % RR_BUFFER_SIZE;
    int b = (rr_idx - n + i     + RR_BUFFER_SIZE) % RR_BUFFER_SIZE;
    float diff = rr_intervals[b] - rr_intervals[a];
    sum_sq += diff * diff;
  }
  return sqrt(sum_sq / (n - 1));
}

// ── EDA reading ───────────────────────────────────────────────────
float readEDA() {
  // Grove GSR: higher conductance = more arousal/stress
  // Returns raw ADC value 0-1023
  return (float)analogRead(EDA_PIN);
}

// ── temperature reading ───────────────────────────────────────────
float readTemp() {
  // LM35: 10mV per °C, 5V ref → 0.004887 V per unit → °C = raw * 0.48828
  // Adjust for your specific sensor
  float raw = analogRead(TEMP_PIN);
  return raw * (5.0 / 1023.0) * 100.0;  // LM35 formula
}

// ── serial output ─────────────────────────────────────────────────
void emitReading() {
  float rmssd = computeRMSSD();
  float eda   = readEDA();
  float temp  = readTemp();
  int   hr    = (bpm > 0 && bpm < 220) ? bpm : 75;  // fallback if no beat yet

  Serial.print(rmssd, 1);
  Serial.print(",");
  Serial.print(eda, 0);
  Serial.print(",");
  Serial.print(temp, 1);
  Serial.print(",");
  Serial.println(hr);
}
