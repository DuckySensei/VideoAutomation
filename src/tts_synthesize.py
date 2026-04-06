"""Text-to-speech via Microsoft Edge TTS (requires network)."""
import asyncio
from pathlib import Path


async def _save_audio(text: str, out_path: Path, voice: str) -> None:
    import edge_tts

    communicate = edge_tts.Communicate(text.strip(), voice)
    await communicate.save(str(out_path))


def synthesize_to_mp3(text: str, out_path: Path, voice: str) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    asyncio.run(_save_audio(text, out_path, voice))
