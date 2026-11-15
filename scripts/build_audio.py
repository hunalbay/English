"""İçerik için gereken ses kliplerini üretir (data/audio/).

Yalnızca eksik ya da metni değişmiş klipler üretilir; artık gerekmeyen dosyalar silinir.
Gereksinimler: ffmpeg, ayrı bir Python ortamında `piper-tts` ve LibriTTS ses modeli.
Ayrıntılar ve lisanslar: docs/AUDIO.md

Kullanım:
    python scripts/build_audio.py --piper-python /yol/tts/bin/python \\
        --model /yol/en-us-libritts-high.onnx [--limit N] [--only words|phrases|lessons] [--check]
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
import wave
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.content.audio import LINE_GAP_MS, MODEL_ID, VOICES, ClipSpec, read_manifest, required_clips  # noqa: E402
from app.content.builder import ContentError, load  # noqa: E402

KIND_OF = {"w": "words", "s": "phrases", "l": "lessons"}


def _encode(wavs: list[Path], target: Path) -> int:
    """WAV parçalarını aralarına sessizlik koyarak tek MP3'e çevirir; süreyi (ms) döndürür."""
    with wave.open(str(wavs[0])) as first:
        rate, width, channels = first.getframerate(), first.getsampwidth(), first.getnchannels()
    silence = b"\x00" * (int(rate * LINE_GAP_MS / 1000) * width * channels)
    frames = []
    for index, path in enumerate(wavs):
        with wave.open(str(path)) as part:
            frames.append(part.readframes(part.getnframes()))
        if index < len(wavs) - 1:
            frames.append(silence)
    pcm = b"".join(frames)
    target.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(  # noqa: S603
        ["ffmpeg", "-loglevel", "error", "-y", "-f", "s16le", "-ar", str(rate), "-ac", str(channels), "-i", "pipe:0",
         "-af", "volume=-1.5dB", "-codec:a", "libmp3lame", "-q:a", "6", "-ac", "1", str(target)],
        input=pcm, check=True,
    )
    return round(len(pcm) / (rate * width * channels) * 1000)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--data-dir", type=Path, default=ROOT / "data")
    parser.add_argument("--piper-python", type=Path, help="piper-tts kurulu Python yorumlayıcısı")
    parser.add_argument("--model", type=Path, help="en-us-libritts-high.onnx dosyası")
    parser.add_argument("--limit", type=int, default=0, help="en çok bu kadar klip üret (0: hepsi)")
    parser.add_argument("--only", choices=sorted(KIND_OF.values()))
    parser.add_argument("--check", action="store_true", help="yalnızca eksikleri say, üretme")
    args = parser.parse_args()

    try:
        content = load(args.data_dir)
    except ContentError as exc:
        print("İçerik doğrulanamadı:", *exc.errors[:20], sep="\n  - ", file=sys.stderr)
        return 1

    audio_dir = args.data_dir / "audio"
    manifest = read_manifest(audio_dir)
    needed = required_clips(content)

    def current(spec: ClipSpec) -> bool:
        entry = manifest.get(spec.key)
        return bool(entry and entry.get("digest") == spec.digest and (audio_dir / spec.filename).is_file())

    missing = [spec for spec in needed.values() if not current(spec)]
    if args.only:
        missing = [spec for spec in missing if KIND_OF[spec.key[0]] == args.only]
    summary = {name: sum(1 for spec in missing if KIND_OF[spec.key[0]] == name) for name in KIND_OF.values()}
    print(f"Gereken klip: {len(needed)}, eksik: {len(missing)} {summary}")
    if args.check:
        return 0
    if args.limit:
        missing = missing[: args.limit]

    if missing:
        if not args.piper_python or not args.model:
            print("Ses üretmek için --piper-python ve --model gereklidir.", file=sys.stderr)
            return 2
        worker = subprocess.Popen(  # noqa: S603
            [str(args.piper_python), str(ROOT / "scripts" / "tts_worker.py"), str(args.model), f"{args.model}.json"],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True, encoding="utf-8",
        )
        failed = 0
        with tempfile.TemporaryDirectory() as tmp:
            for done, spec in enumerate(missing, 1):
                parts = []
                ok = True
                for index, (voice, text) in enumerate(spec.lines):
                    out = Path(tmp) / f"part{index}.wav"
                    worker.stdin.write(json.dumps({"speaker": VOICES[voice], "text": text, "out": str(out)}) + "\n")
                    worker.stdin.flush()
                    reply = json.loads(worker.stdout.readline() or '{"ok": false, "error": "süreç sonlandı"}')
                    if not reply.get("ok"):
                        print(f"  ! {spec.key}: {reply.get('error')}", file=sys.stderr)
                        ok = False
                        break
                    parts.append(out)
                if not ok:
                    failed += 1
                    continue
                duration = _encode(parts, audio_dir / spec.filename)
                manifest[spec.key] = {"file": spec.filename, "digest": spec.digest, "ms": duration}
                if done % 200 == 0:
                    _write_manifest(audio_dir, manifest)
                    print(f"  {done}/{len(missing)}", flush=True)
        worker.stdin.close()
        worker.wait(timeout=30)
        if failed:
            print(f"{failed} klip üretilemedi.", file=sys.stderr)

    # Artık gerekmeyen kayıtları ve dosyaları temizle
    valid = {spec.key: spec for spec in needed.values()}
    manifest = {
        key: entry for key, entry in manifest.items()
        if key in valid and entry.get("digest") == valid[key].digest and (audio_dir / entry["file"]).is_file()
    }
    keep = {entry["file"] for entry in manifest.values()}
    removed = 0
    for path in (audio_dir / "clips").rglob("*.mp3") if (audio_dir / "clips").is_dir() else []:
        if path.relative_to(audio_dir).as_posix() not in keep:
            path.unlink()
            removed += 1
    _write_manifest(audio_dir, manifest)
    total_ms = sum(entry["ms"] for entry in manifest.values())
    size = sum((audio_dir / entry["file"]).stat().st_size for entry in manifest.values())
    print(f"Hazır klip: {len(manifest)} / {len(needed)}; toplam süre {total_ms / 60000:.1f} dk, "
          f"boyut {size / 1e6:.1f} MB; silinen eski dosya: {removed}")
    return 0


def _write_manifest(audio_dir: Path, clips: dict[str, dict]) -> None:
    audio_dir.mkdir(parents=True, exist_ok=True)
    payload = {"model": MODEL_ID, "voices": VOICES, "clips": dict(sorted(clips.items()))}
    tmp = audio_dir / "manifest.json.tmp"
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=0, separators=(",", ":")) + "\n", encoding="utf-8")
    tmp.replace(audio_dir / "manifest.json")


if __name__ == "__main__":
    raise SystemExit(main())
