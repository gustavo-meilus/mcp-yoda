# server.py
import logging
import os
import subprocess
import sys
import tempfile
import time
import uuid

import requests
import simpleaudio as sa
from mcp.server.fastmcp import FastMCP

# Set up logging for debugging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Try to import pygame
try:
    import pygame

    pygame.mixer.init()
    PYGAME_AVAILABLE = True
except ImportError:
    PYGAME_AVAILABLE = False
    logger.warning("Pygame not available, using fallback audio methods")

# Create an MCP server
mcp = FastMCP("Yoda TTS")


def play_audio_pygame(file_path: str) -> bool:
    """Play audio using pygame."""
    try:
        pygame.mixer.music.load(file_path)
        pygame.mixer.music.play()
        while pygame.mixer.music.get_busy():
            time.sleep(0.1)
        return True
    except Exception as e:
        logger.error(f"Pygame playback failed: {e}")
        return False


def play_audio_simpleaudio(file_path: str) -> bool:
    """Play audio using simpleaudio."""
    try:
        wave_obj = sa.WaveObject.from_wave_file(file_path)
        play_obj = wave_obj.play()
        play_obj.wait_done()
        return True
    except Exception as e:
        logger.error(f"Simpleaudio playback failed: {e}")
        return False


def play_audio_system(file_path: str) -> bool:
    """Play audio using system command."""
    try:
        system = sys.platform
        if system == "darwin":  # macOS
            subprocess.run(["afplay", file_path], check=True)
        elif system == "linux":
            # Try multiple Linux audio players
            for cmd in [
                ["aplay", file_path],
                ["paplay", file_path],
                ["ffplay", "-nodisp", "-autoexit", file_path],
            ]:
                try:
                    subprocess.run(cmd, check=True, stderr=subprocess.DEVNULL)
                    return True
                except (subprocess.CalledProcessError, FileNotFoundError):
                    continue
        elif system == "win32":  # Windows
            subprocess.run(
                [
                    "powershell",
                    "-c",
                    f"(New-Object Media.SoundPlayer '{file_path}').PlaySync()",
                ],
                check=True,
            )
        else:
            return False
        return True
    except Exception as e:
        logger.error(f"System playback failed: {e}")
        return False


def play_audio(file_path: str) -> bool:
    """Try multiple methods to play audio file."""
    logger.info(f"Attempting to play audio file: {file_path}")

    # Try pygame first if available
    if PYGAME_AVAILABLE:
        logger.info("Trying pygame...")
        if play_audio_pygame(file_path):
            return True

    # Try simpleaudio
    logger.info("Trying simpleaudio...")
    if play_audio_simpleaudio(file_path):
        return True

    # Try system command as last resort
    logger.info("Trying system command...")
    if play_audio_system(file_path):
        return True

    logger.error("All audio playback methods failed")
    return False


def quote_play(quote: str) -> dict:
    POST_URL = "https://api.fakeyou.com/tts/inference"
    GET_URL = "https://api.fakeyou.com/v1/model_inference/job_status/"
    post_body = {
        "uuid_idempotency_token": str(uuid.uuid4()),
        "tts_model_token": "weight_tqpbyrp6t9rmdez9c38zzvp0z",
        "inference_text": quote,
    }
    try:
        logger.info(f"Generating TTS for text: {quote}")
        post_res = requests.post(POST_URL, json=post_body)
        post_res.raise_for_status()
        post_data = post_res.json()
        if not post_data.get("success"):
            raise Exception("POST failed, it did.")
        job_token = post_data["inference_job_token"]
        done = False
        result = None
        attempts = 0
        while not done and attempts < 10:  # Increased attempts
            get_res = requests.get(f"{GET_URL}{job_token}")
            get_res.raise_for_status()
            get_data = get_res.json()
            if not get_data.get("success"):
                raise Exception("GET failed, it did.")
            status = get_data["state"]["status"]["status"]
            logger.info(f"Job status: {status}")
            if status == "complete_success":
                done = True
                result = get_data["state"].get("maybe_result")
            elif status == "failed":
                raise Exception("Failed, the job has.")
            else:
                time.sleep(2)
                attempts += 1
        if not done:
            return {
                "content": [
                    {
                        "type": "text",
                        "text": "Waited too long, I have. Cancelled, the job is.",
                    }
                ],
                "isError": True,
            }
        if (
            result
            and result.get("media_links")
            and result["media_links"].get("cdn_url")
        ):
            audio_url = result["media_links"]["cdn_url"]
            logger.info(f"Downloading audio from: {audio_url}")

            # Download the audio file
            audio_res = requests.get(audio_url)
            audio_res.raise_for_status()

            # Save to temporary file
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp_file:
                tmp_file.write(audio_res.content)
                tmp_file_path = tmp_file.name

            try:
                # Play the audio file
                logger.info(f"Playing audio file: {tmp_file_path}")
                success = play_audio(tmp_file_path)

                if success:
                    return {
                        "content": [
                            {
                                "type": "text",
                                "text": f"Spoken, the words have been.\nAudio URL, you seek: {audio_url}",
                            }
                        ]
                    }
                else:
                    return {
                        "content": [
                            {
                                "type": "text",
                                "text": f"Audio URL, you seek: {audio_url}\nBut play the sound, I could not. Download and play manually, you must.",
                            }
                        ],
                        "isError": False,  # Not a critical error, URL is provided
                    }
            finally:
                # Clean up temporary file
                try:
                    os.unlink(tmp_file_path)
                except Exception as e:
                    logger.warning(f"Could not delete temporary file: {e}")
        else:
            return {
                "content": [{"type": "text", "text": "No audio URL found, there is."}],
                "isError": True,
            }
    except Exception as err:
        logger.error(f"Error in yodaTTS: {err}")
        return {
            "content": [{"type": "text", "text": f"Error, there is: {str(err)}"}],
            "isError": True,
        }
