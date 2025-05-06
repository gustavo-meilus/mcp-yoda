import os
import torch

os.environ["TORCH_FORCE_NO_WEIGHTS_ONLY_LOAD"] = "1"

from TTS.api import TTS

AUDIO_INPUT = "speaker/yoda.wav"
AUDIO_OUTPUT = "output.wav"

TEXT = "It took me quite a long time to develop a voice, and now that I have it I'm not going to be silent."


device = "cuda" if torch.cuda.is_available() else "cpu"


tts = TTS("tts_models/multilingual/multi-dataset/xtts_v2").to(device)

# generate speech by cloning a voice using default settings
tts.tts_to_file(
    text=TEXT,
    file_path=AUDIO_OUTPUT,
    speaker_wav=AUDIO_INPUT,
    language="en",
    split_sentences=True,
)
