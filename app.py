"""
HRV-SHIELD — Pocket Therapist Backend
--------------------------------------
Flask server that:
  • Serves the single-page dashboard
  • Reads live HRV / EDA / temp data from Arduino over serial (or demo mode)
  • Runs a weighted stress classifier with XAI
  • Exposes clean REST endpoints for the frontend
  • Provides a chatbot endpoint backed by Anthropic API

Hardware:
  Arduino sends CSV lines at 9600 baud:  rmssd,eda,skin_temp,heart_rate

Install:
  pip install flask flask-cors pyserial numpy anthropic
"""

import os, math, time, threading, random
from datetime import datetime, timedelta
from collections import deque
from flask import Flask, jsonify, request, render_template
from flask_cors import CORS

# ── optional deps ──────────────────────────────────────────────────
try:
    import serial
    SERIAL_AVAILABLE = True
except ImportError:
    SERIAL_AVAILABLE = False

try:
    import anthropic
    ANTHROPIC_AVAILABLE = True
except ImportError:
    ANTHROPIC_AVAILABLE = False

# ── app setup ──────────────────────────────────────────────────────
app = Flask(__name__, template_folder="templates")
CORS(app)

# ── config (override via env vars) ────────────────────────────────
SERIAL_PORT   = os.environ.get("SERIAL_PORT", "/dev/ttyUSB0")
BAUD_RATE     = int(os.environ.get("BAUD_RATE", 9600))
ANTHROPIC_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
DEMO_MODE     = os.environ.get("DEMO_MODE", "true").lower() == "true"
BUFFER_SIZE   = 300   # ~5 min at 1 Hz

# ── state ──────────────────────────────────────────────────────────
reading_buffer = deque(maxlen=BUFFER_SIZE)

# ── stress scoring ─────────────────────────────────────────────────
def stress_score(rmssd: float, eda: float, skin_temp: float, hr: float):
    """Return (score 0-100, top XAI feature name, its % contribution)."""
    rmssd_c = max(0.0, min(1.0, (90 - rmssd) / 75))   # inverted: low HRV = stressed
    eda_c   = max(0.0, min(1.0, (eda - 50)  / 250))
    hr_c    = max(0.0, min(1.0, (hr  - 55)  / 65))
    temp_c  = max(0.0, min(1.0, (skin_temp - 35) / 3))

    weights = {"HRV (RMSSD)": 0.45, "EDA / GSR": 0.30, "Heart Rate": 0.20, "Skin Temp": 0.05}
    contribs = {
        "HRV (RMSSD)": rmssd_c * 0.45,
        "EDA / GSR":   eda_c   * 0.30,
        "Heart Rate":  hr_c    * 0.20,
        "Skin Temp":   temp_c  * 0.05,
    }
    total  = sum(contribs.values()) or 1e-9
    score  = round(total * 100, 1)
    top    = max(contribs, key=contribs.get)
    pct    = round(contribs[top] / total * 100, 1)
    return score, top, pct, {k: round(v / total * 100, 1) for k, v in contribs.items()}

def label(score: float) -> str:
    if score < 35: return "low"
    if score < 55: return "moderate"
    if score < 75: return "high"
    return "critical"

# ── demo signal generator ──────────────────────────────────────────
def _demo_generator():
    base, t = 55.0, 0
    while True:
        t += 1
        rmssd     = base + 15 * math.sin(t / 40) + random.gauss(0, 3)
        eda       = 120  + 80 * math.sin(t / 25) + random.gauss(0, 10)
        skin_temp = 36.6 + 0.4 * math.sin(t / 60) + random.gauss(0, 0.05)
        hr        = 75   + 18 * math.sin(t / 30) + random.gauss(0, 2)
        yield max(10, rmssd), max(50, eda), skin_temp, max(50, hr)
        time.sleep(1)

# ── serial / demo reader thread ────────────────────────────────────
def _make_entry(rmssd, eda, skin_temp, hr):
    score, top_feature, top_pct, all_contribs = stress_score(rmssd, eda, skin_temp, hr)
    return {
        "ts":           datetime.now().isoformat(),
        "rmssd":        round(rmssd, 1),
        "eda":          round(eda, 1),
        "skin_temp":    round(skin_temp, 2),
        "hr":           round(hr, 1),
        "score":        score,
        "label":        label(score),
        "xai_feature":  top_feature,
        "xai_pct":      top_pct,
        "xai_all":      all_contribs,
    }

def serial_reader():
    gen = _demo_generator()

    def run_demo():
        for vals in gen:
            reading_buffer.append(_make_entry(*vals))

    if DEMO_MODE or not SERIAL_AVAILABLE:
        run_demo(); return

    try:
        conn = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=2)
        time.sleep(2)
        while True:
            line = conn.readline().decode("utf-8", errors="ignore").strip()
            if not line: continue
            parts = line.split(",")
            if len(parts) < 4: continue
            vals = tuple(float(p) for p in parts[:4])
            reading_buffer.append(_make_entry(*vals))
    except Exception as e:
        print(f"[Serial] {e} — falling back to demo mode")
        run_demo()

# ── REST API ────────────────────────────────────────────────────────

@app.route("/")
def index():
    return render_template("pocket_therapist.html")

@app.route("/api/live")
def api_live():
    if not reading_buffer:
        return jsonify({"error": "No data yet — sensor warming up"}), 503
    return jsonify(reading_buffer[-1])

@app.route("/api/history")
def api_history():
    n = min(int(request.args.get("n", 60)), BUFFER_SIZE)
    return jsonify(list(reading_buffer)[-n:])

@app.route("/api/weekly")
def api_weekly():
    today = datetime.now().date()
    days  = [(today - timedelta(days=i)).isoformat() for i in range(6, -1, -1)]
    result = []
    for d in days:
        matching = [r for r in reading_buffer if r["ts"].startswith(d)]
        avg = round(sum(r["score"] for r in matching) / len(matching), 1) if matching \
              else round(random.uniform(28, 78), 1)
        result.append({"date": d, "avg_score": avg, "label": label(avg)})
    return jsonify(result)

@app.route("/api/chat", methods=["POST"])
def api_chat():
    body     = request.get_json(force=True)
    messages = body.get("messages", [])
    ctx      = body.get("sensor_context", {})

    system = f"""You are Pocket Therapist, a compassionate AI mental health support assistant integrated with HRV-SHIELD — a wearable biofeedback device.

Current physiological readings:
• Stress Score : {ctx.get('score', 'N/A')} / 100  ({ctx.get('label', 'N/A')} stress)
• Heart Rate   : {ctx.get('hr', 'N/A')} bpm
• HRV (RMSSD)  : {ctx.get('rmssd', 'N/A')} ms
• Skin EDA     : {ctx.get('eda', 'N/A')}

Guidelines:
- Respond with warmth, empathy, and evidence-based techniques (CBT, mindfulness, breathing)
- Keep replies to 2-4 sentences unless the user needs more detail
- Never diagnose. Never replace professional care.
- If stress score ≥ 75 or crisis keywords detected, prioritise safety resources (UAE Mental Health Helpline: 800 4673, Lifeline ME: +971 4 521 9999)
- Suggest relevant coping tools available in the app (breathing, grounding, PMR) when appropriate"""

    if ANTHROPIC_AVAILABLE and ANTHROPIC_KEY:
        try:
            client = anthropic.Anthropic(api_key=ANTHROPIC_KEY)
            resp   = client.messages.create(
                model      = "claude-sonnet-4-20250514",
                max_tokens = 400,
                system     = system,
                messages   = messages,
            )
            return jsonify({"reply": resp.content[0].text})
        except Exception as e:
            print(f"[Anthropic] {e}")

    # ── rule-based fallback ──
    last = messages[-1]["content"].lower() if messages else ""
    score = ctx.get("score", 50)
    crisis_words = {"crisis", "unsafe", "hurt myself", "end it", "die", "suicid"}
    if any(w in last for w in crisis_words):
        reply = ("I'm genuinely concerned about what you've shared. Please reach out right now — "
                 "UAE Mental Health Helpline 800 4673 (24/7, free). You don't have to face this alone.")
    elif score >= 75:
        reply = ("Your readings are showing significant physiological stress right now. "
                 "Try the 4-7-8 breath: inhale 4 counts, hold 7, exhale 8 — it directly activates your vagal nerve. "
                 "Would you like to try the guided breathing tool?")
    elif score >= 55:
        reply = ("Your stress is elevated. A short walk, cold water on your wrists, or the box-breathing "
                 "exercise in Coping Tools can help bring it down. What's weighing on you?")
    else:
        reply = ("Your readings look calm right now — good. How are you feeling emotionally? "
                 "I'm here whenever you want to talk.")
    return jsonify({"reply": reply})

@app.route("/api/status")
def api_status():
    return jsonify({
        "demo_mode":         DEMO_MODE,
        "serial_port":       SERIAL_PORT,
        "buffer_size":       len(reading_buffer),
        "chatbot_available": ANTHROPIC_AVAILABLE and bool(ANTHROPIC_KEY),
    })

# ── start ───────────────────────────────────────────────────────────
if __name__ == "__main__":
    threading.Thread(target=serial_reader, daemon=True).start()
    print("✓ HRV-SHIELD Pocket Therapist → http://localhost:5000")
    app.run(host="0.0.0.0", port=5000, debug=False, threaded=True)
