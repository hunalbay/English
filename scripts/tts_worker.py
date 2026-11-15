"""Piper ile ses üreten yardımcı süreç (yalnızca `piper-tts` paketine ihtiyaç duyar).

Standart girdiden satır satır JSON iş alır: {"speaker": 45, "text": "...", "out": "dosya.wav"}
Her iş bitince standart çıktıya {"out": ..., "ok": true} yazar. scripts/build_audio.py tarafından çağrılır.
"""

from __future__ import annotations

import json
import sys
import wave

from piper import PiperVoice, SynthesisConfig


def main() -> int:
    model, config = sys.argv[1], sys.argv[2]
    voice = PiperVoice.load(model, config)
    for raw in sys.stdin:
        raw = raw.strip()
        if not raw:
            continue
        job = json.loads(raw)
        try:
            with wave.open(job["out"], "wb") as wav_file:
                voice.synthesize_wav(job["text"], wav_file, SynthesisConfig(speaker_id=job["speaker"]))
            result = {"out": job["out"], "ok": True}
        except Exception as exc:  # noqa: BLE001 (iş başarısızsa bildir, sıradakine geç)
            result = {"out": job["out"], "ok": False, "error": str(exc)}
        sys.stdout.write(json.dumps(result) + "\n")
        sys.stdout.flush()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
