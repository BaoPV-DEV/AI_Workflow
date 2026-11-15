"""Giọng đọc chạy local/miễn phí. Trả về (wav, word_timings hoặc None)."""
from __future__ import annotations

import asyncio
import shutil
import subprocess
from pathlib import Path

from .util import ffmpeg, run

SR = 48000


class TTSError(RuntimeError):
    pass


def synth(text: str, out_wav: Path, engine: str, voice: str, rate: str = "+0%", piper_model: str = "",
          lang: str = "vi"):
    """Trả về (wav, word_timings | None, engine_đã_dùng). engine 'auto' = edge-tts, lỗi thì gTTS.
    Không bao giờ âm thầm ra file câm: lỗi hết thì báo TTSError (trừ khi chọn 'silent')."""
    out_wav.parent.mkdir(parents=True, exist_ok=True)
    if not text.strip() or engine == "silent":
        secs = max(1.5, len(text.split()) / 2.6)  # ~156 từ/phút
        _silence(out_wav, secs)
        return out_wav, None, "silent"
    chain = {"auto": ["edge", "gtts"]}.get(engine, [engine])
    errors = []
    for eng in chain:
        try:
            if eng == "edge":
                wav, words = _edge(text, out_wav, voice, rate)
            elif eng == "gtts":
                wav, words = _gtts(text, out_wav, lang)
            elif eng == "piper":
                wav, words = _piper(text, out_wav, piper_model)
            elif eng == "kokoro":
                wav, words = _kokoro(text, out_wav, voice)
            else:
                raise ValueError(f"TTS engine không hỗ trợ: {eng}")
            return wav, words, eng
        except Exception as e:  # thử engine kế tiếp
            errors.append(f"{eng}: {type(e).__name__}: {str(e)[:200]}")
    raise TTSError("Không tạo được giọng đọc.\n  " + "\n  ".join(errors) +
                   "\n  → Kiểm tra internet; cập nhật: pip install -U edge-tts gTTS")


def _silence(out: Path, secs: float) -> None:
    run([ffmpeg(), "-y", "-v", "error", "-f", "lavfi", "-i", f"anullsrc=r={SR}:cl=mono",
         "-t", f"{secs:.2f}", out])


def _to_wav(src: Path, out: Path) -> None:
    run([ffmpeg(), "-y", "-v", "error", "-i", src, "-ar", str(SR), "-ac", "1", out])


def _edge(text: str, out: Path, voice: str, rate: str):
    try:
        import edge_tts
    except ImportError as e:
        raise RuntimeError("pip install edge-tts") from e

    async def go():
        try:  # edge-tts >= 7 mặc định trả SentenceBoundary; xin WordBoundary để có mốc từng từ
            com = edge_tts.Communicate(text, voice, rate=rate, boundary="WordBoundary")
        except TypeError:
            com = edge_tts.Communicate(text, voice, rate=rate)
        audio, words = bytearray(), []
        async for ch in com.stream():
            if ch["type"] == "audio":
                audio.extend(ch["data"])
            elif ch["type"] == "WordBoundary":
                s = ch["offset"] / 1e7
                words.append({"word": ch["text"], "start": round(s, 3), "end": round(s + ch["duration"] / 1e7, 3)})
        return bytes(audio), words

    try:  # chặn treo vô thời hạn khi mạng tới máy chủ edge-tts bị nghẽn (không lỗi, chỉ im lặng)
        audio, words = asyncio.run(asyncio.wait_for(go(), timeout=25))
    except asyncio.TimeoutError as e:
        raise RuntimeError("edge-tts không phản hồi sau 25s (mạng có thể bị chặn/nghẽn)") from e
    if len(audio) < 2000:
        raise RuntimeError(f"edge-tts trả về âm thanh rỗng (giọng '{voice}' có đúng không?)")
    mp3 = out.with_suffix(".mp3")
    mp3.write_bytes(audio)
    _to_wav(mp3, out)
    mp3.unlink(missing_ok=True)
    return out, (words or None)


def _gtts(text: str, out: Path, lang: str):
    """Dự phòng: Google Translate TTS (miễn phí, cần internet, không có mốc từng từ)."""
    try:
        from gtts import gTTS
    except ImportError as e:
        raise RuntimeError("pip install gTTS") from e
    from . import config

    mp3 = out.with_suffix(".g.mp3")
    gTTS(text, lang=config.language(lang)["gtts"]).save(str(mp3))
    _to_wav(mp3, out)
    mp3.unlink(missing_ok=True)
    return out, None


def _piper(text: str, out: Path, model: str):
    exe = shutil.which("piper")
    if not exe or not model:
        raise RuntimeError("Cần cài piper và đặt tts.piper_model trong settings.yaml")
    raw = out.with_suffix(".piper.wav")
    subprocess.run([exe, "--model", model, "--output_file", str(raw)], input=text, text=True, check=True)
    _to_wav(raw, out)
    raw.unlink(missing_ok=True)
    return out, None


def _kokoro(text: str, out: Path, voice: str):
    try:
        import numpy as np
        import soundfile as sf
        from kokoro import KPipeline
    except ImportError as e:
        raise RuntimeError("pip install kokoro soundfile (Kokoro chưa hỗ trợ tiếng Việt)") from e
    pipe = KPipeline(lang_code=voice[:1] if voice else "a")
    chunks = [a for _, _, a in pipe(text, voice=voice or "af_heart")]
    raw = out.with_suffix(".k.wav")
    sf.write(raw, np.concatenate(chunks), 24000)
    _to_wav(raw, out)
    raw.unlink(missing_ok=True)
    return out, None
