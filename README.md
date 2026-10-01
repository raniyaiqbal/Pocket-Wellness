# Pocket Wellness

**A multimodal, explainable wearable system for real-time stress monitoring and graduated intervention.**

B.Eng (Hons) Mechatronics Engineering thesis (ECTE498), University of Wollongong in Dubai, 2026. Supervised by Dr. Obada Al Khatib.

📄 **[Read the full thesis (PDF)](docs/Pocket-Wellness-Thesis.pdf)**

---

## Overview

Pocket Wellness captures three physiological signals and turns them into a live, explainable stress score:

- **HRV** (heart rate variability), from a consumer smartwatch via photoplethysmography
- **GSR / EDA** (electrodermal activity), from a Grove GSR sensor
- **EMG** (surface electromyography), from a MyoWare sensor

The two low-cost sensors are bridged through an **Arduino Nano ESP32**. Signals are reduced to an 18-feature vector and classified by a **Random Forest** into one of four stress tiers (Low, Moderate, High, Critical). A **Stress Score Fusion Engine** combines the modality-specific outputs into one composite score, and a **SHAP** explainability layer shows which signals drove each prediction.

The score feeds a **four-tier intervention framework**. It starts with guided breathing and grounding exercises, moves to a physiologically aware chatbot, and ends with a **dual-pathway crisis escalation**. Escalation is triggered independently by sustained physiological thresholds and by crisis-language detection.

## Key results

These figures come from the thesis and were measured on a modeled dataset. Read the caveat below them.

| Metric | Result |
|---|---|
| Random Forest test accuracy (18 features) | 97.4% (tied with k-NN, ahead of SVM, Logistic Regression, Gradient Boosting and Decision Tree) |
| Single-modality accuracy | HRV 73.7% · GSR 71.1% · EMG 86.8% (this spread is the case for fusing all three) |
| MDI / SHAP feature-importance agreement | Spearman ρ = 0.94 |
| Intervention modules | All 7 produced statistically significant stress-score reductions (p < 0.05) |

> **Scope note:** this is a pre-clinical proof of concept, not a medical device. No live-participant study was run. The classifier was trained and evaluated on a dataset modeled from public Kaggle physiological and mental-health data and calibrated to standard stress-induction protocols. The hardware and software pipeline was tested end to end by the author.

## What's in this repository

```
pocket-wellness/
├── app.py                          # Flask backend: sensor reader, stress scoring + XAI, REST API, chatbot
├── templates/
│   └── pocket_therapist.html       # Single-page dashboard UI
├── firmware/
│   └── hrv_shield_sensors/
│       └── hrv_shield_sensors.ino  # Arduino / ESP32 sensor firmware (1 Hz CSV over serial)
├── docs/
│   └── Pocket-Wellness-Thesis.pdf  # Full thesis
└── requirements.txt
```

This repository holds the **dashboard prototype** ("Pocket Therapist", HRV-SHIELD v2). Its backend scores stress with a lightweight weighted formula and per-feature contribution bars, so it runs on any laptop without scikit-learn. The full ML pipeline (feature extraction, the Random Forest, SHAP, the fusion engine and crisis detection) is documented in **Appendix A of the thesis**.

### Dashboard pages

- **Dashboard**: live stress gauge, explainability bars, sparklines and a trend chart
- **Disorder Monitor**: stress, anxiety, panic, insomnia, depression and burnout indicators
- **Trends**: 7-day chart, best and worst day, trend direction
- **AI Therapist**: chatbot that sees the live sensor context, with a mood selector and crisis links
- **Coping Tools**: box breathing, 4-7-8, 5-4-3-2-1 grounding, PMR, diaphragmatic breathing, sleep hygiene
- **Crisis Support**: UAE helplines and a safety check-in with escalation logic
- **Profile**: privacy toggles, UAE PDPL compliance information, data deletion

## Quick start

```bash
pip install -r requirements.txt
python app.py
```

Then open **http://localhost:5000**.

The app runs in **demo mode** by default, using simulated sensor signals, so you don't need any hardware to try the full UI.

### With real hardware

1. Flash `firmware/hrv_shield_sensors/hrv_shield_sensors.ino` to your Arduino or ESP32.
   - Pulse sensor → A0 · GSR sensor → A1 · LM35 temperature sensor → A2
2. Run the backend against the serial port:
   ```bash
   DEMO_MODE=false SERIAL_PORT=/dev/ttyUSB0 python app.py
   ```
   On macOS the port is usually `/dev/tty.usbserial-*` or `/dev/tty.SLAB_USBtoUART`. On Windows, use a `COM` port.

### AI chatbot (optional)

Set an Anthropic API key to enable LLM-powered replies:

```bash
ANTHROPIC_API_KEY=sk-ant-... python app.py
```

Without a key, the chatbot uses a built-in rule-based fallback that still handles crisis keywords.

### Environment variables

| Variable | Default | Purpose |
|---|---|---|
| `DEMO_MODE` | `true` | Use simulated signals instead of serial input |
| `SERIAL_PORT` | `/dev/ttyUSB0` | Serial port for the sensor board |
| `BAUD_RATE` | `9600` | Serial baud rate |
| `ANTHROPIC_API_KEY` | (none) | Enables the LLM chatbot |

## API

| Endpoint | Description |
|---|---|
| `GET /api/live` | Latest reading: signals, stress score, tier and feature contributions |
| `GET /api/history?n=60` | The last *n* readings (buffer holds about 5 minutes at 1 Hz) |
| `GET /api/weekly` | 7-day average stress per day |
| `POST /api/chat` | Chatbot reply, given `messages` and `sensor_context` |
| `GET /api/status` | Demo mode, serial port, buffer size and chatbot availability |

## Tech stack

Python · Flask · NumPy · pySerial · Anthropic API · HTML/CSS/JavaScript · Arduino (C++) · ESP32
Thesis ML pipeline: scikit-learn (Random Forest) · SHAP · SciPy signal processing

## Crisis resources (UAE)

| Service | Number |
|---|---|
| UAE Mental Health Helpline | 800 4673 (24/7, free, EN/AR) |
| Lifeline Middle East | +971 4 521 9999 |
| Emergency | 999 |

⚕️ *Pocket Wellness is a non-diagnostic research prototype. It does not replace professional care.*

## Author

**Raniya Iqbal**, Mechatronics Engineer · [Portfolio](https://raniyaiqbal.github.io) · [LinkedIn](https://www.linkedin.com/in/raniya-iqbal)
