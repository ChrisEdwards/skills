"""Resident Pocket TTS server.

Holds the model in memory so each utterance costs ~130ms to first audio
instead of paying a 1.1s model load every time. Streams raw PCM as it is
generated, so playback starts before synthesis finishes.

Wire format on POST /say: raw s16le, 24000 Hz, mono. Chunked.
"""

import json
import logging
import os
import secrets
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from normalize import normalize  # noqa: E402

HOST = "127.0.0.1"
PORT = int(os.environ.get("AGENT_TTS_PORT", "7711"))
MODEL = os.environ.get("AGENT_TTS_MODEL", "mlx-community/pocket-tts")
DEFAULT_VOICE = os.environ.get("AGENT_TTS_VOICE", "alba")
SAMPLE_RATE = 24000

# The model samples at temperature 0.7 by default, so the same text renders
# as a different take every run. Seeding makes it byte-identical. Lower
# temperature gives steadier delivery at the cost of some liveliness.
#
# Seed 99 was chosen by ear on 2026-09-19 from a blind set of takes.
# Seed 42 was the runner-up and sounded nearly as good, so if 99 starts to
# grate, try AGENT_TTS_SEED=42 before changing voice or temperature.
DEFAULT_SEED = int(os.environ.get("AGENT_TTS_SEED", "99"))
DEFAULT_TEMP = float(os.environ.get("AGENT_TTS_TEMP", "0.7"))

VOICES = ["alba", "azelma", "cosette", "eponine",
          "fantine", "javert", "jean", "marius"]

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
log = logging.getLogger("agent-tts")

_model = None
_lock = threading.Lock()   # MLX generation is not safe to run concurrently


def get_model():
    global _model
    if _model is None:
        from mlx_audio.tts.utils import load_model
        log.info("loading %s", MODEL)
        _model = load_model(MODEL)
        # One throwaway generation compiles the graph, so the first real
        # request is not slower than the rest.
        list(_model.generate(text="ready", voice=DEFAULT_VOICE))
        log.info("ready")
    return _model


def to_pcm16(a):
    a = np.asarray(a, dtype=np.float32)
    return (np.clip(a, -1.0, 1.0) * 32767.0).astype("<i2").tobytes()


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, *args):
        pass

    def _json(self, code, obj):
        body = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path.startswith("/health"):
            self._json(200, {"ok": True, "model": MODEL,
                             "loaded": _model is not None,
                             "voice": DEFAULT_VOICE, "voices": VOICES})
        else:
            self._json(404, {"error": "not found"})

    def do_POST(self):
        if not self.path.startswith("/say"):
            self._json(404, {"error": "not found"})
            return
        try:
            n = int(self.headers.get("Content-Length", 0))
            req = json.loads(self.rfile.read(n) or b"{}")
        except Exception as e:
            self._json(400, {"error": f"bad request: {e}"})
            return

        text = (req.get("text") or "").strip()
        if not text:
            self._json(400, {"error": "no text"})
            return
        voice = req.get("voice") or DEFAULT_VOICE
        if voice not in VOICES:
            voice = DEFAULT_VOICE
        try:
            seed = int(req.get("seed", DEFAULT_SEED))
        except (TypeError, ValueError):
            seed = DEFAULT_SEED
        try:
            temp = float(req.get("temperature", DEFAULT_TEMP))
        except (TypeError, ValueError):
            temp = DEFAULT_TEMP
        if req.get("normalize", True):
            text = normalize(text)
        if not text:
            self._json(400, {"error": "text empty after normalisation"})
            return

        log.info("say [%s seed=%s temp=%s] %s", voice, seed, temp,
                 text[:60] + ("..." if len(text) > 60 else ""))
        m = get_model()

        self.send_response(200)
        self.send_header("Content-Type", "audio/L16; rate=24000; channels=1")
        self.send_header("Transfer-Encoding", "chunked")
        self.send_header("X-Spoken-Text", text[:400].encode("ascii", "replace").decode())
        self.end_headers()

        try:
            with _lock:
                import mlx.core as mx
                # A negative seed means "give me a fresh take". Skipping the
                # seed call is not enough, the RNG state does not reliably
                # advance between requests, so pick an explicit random one.
                mx.random.seed(seed if seed >= 0 else secrets.randbelow(2**31))
                for seg in m.generate(text=text, voice=voice, stream=True,
                                      temperature=temp):
                    chunk = to_pcm16(seg.audio)
                    if not chunk:
                        continue
                    self.wfile.write(f"{len(chunk):X}\r\n".encode())
                    self.wfile.write(chunk)
                    self.wfile.write(b"\r\n")
                    self.wfile.flush()
            self.wfile.write(b"0\r\n\r\n")
            self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError):
            log.info("client disconnected mid-stream")


def main():
    get_model()
    srv = ThreadingHTTPServer((HOST, PORT), Handler)
    log.info("listening on http://%s:%d", HOST, PORT)
    srv.serve_forever()


if __name__ == "__main__":
    main()
