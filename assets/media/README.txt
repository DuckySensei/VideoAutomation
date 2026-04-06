Place your licensed media here (names must match assets/licenses/manifest.csv):

  sample_bg_001.mp4   — vertical or horizontal background video (any length; output uses -shortest)
  sample_music_001.mp3 — audio bed (music or voice track)

Install FFmpeg and ensure `ffmpeg` is on your PATH, then run:

  python src/main.py --base-dir . --script-max-items 1

The pipeline will mux background + audio + subtitles into output/renders/<id>.mp4

Long background clip (e.g. 30 minutes):
  Copy to sample_bg_001.mp4 (or keep manifest paths in sync), then set
  config/render_config.json — see config/render_config.example.json
  (start_sec = where to begin, duration_sec = how many seconds to use from that clip).

Background noise on the audio file:
  Optional FFmpeg cleanup: "audio.denoise": "light" or "medium" in render_config.json
  (helps a bit; heavy noise needs Audacity / iZotope / pro tools).

TTS + 9:16 (default when config/render_config.json has tts.enabled true):
  Voice is generated from the script (edge-tts). Original gameplay audio is not mixed in.
  Long clips: random start + segment length = narration length (see config/render_config.example.json).
