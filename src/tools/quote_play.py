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

    try:
        pygame.mixer.init()
        PYGAME_AVAILABLE = True
        logger.info("Pygame initialized successfully")
    except pygame.error as e:
        PYGAME_AVAILABLE = False
        logger.warning(f"Pygame mixer initialization failed: {e}")
        logger.info("Will use fallback audio methods")
except ImportError:
    PYGAME_AVAILABLE = False
    logger.warning("Pygame not available, using fallback audio methods")

# Create an MCP server
mcp = FastMCP("Yoda TTS")


def play_audio_pygame(file_path: str) -> bool:
    """Play audio using pygame."""
    if not PYGAME_AVAILABLE:
        logger.debug("Pygame not available, skipping pygame playback")
        return False
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

    # Add headers that might be required
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36",
    }

    # List of Yoda models to try in order of preference
    yoda_models = [
        ("weight_8ye42btvd3ybnc6srbghr2ap2", "Yoda (Version 1.0)"),
        ("weight_tqpbyrp6t9rmdez9c38zzvp0z", "Yoda (Version 2.0)"),
    ]

    last_error = None

    for model_token, model_name in yoda_models:
        logger.info(f"Trying model: {model_name}")

        post_body = {
            "uuid_idempotency_token": str(uuid.uuid4()),
            "tts_model_token": model_token,
            "inference_text": quote,
        }

        try:
            logger.info(f"Generating TTS for text: {quote}")
            post_res = requests.post(
                POST_URL, json=post_body, headers=headers, timeout=10
            )

            # Check for rate limiting
            if post_res.status_code == 429:
                logger.warning("Rate limited by API")
                last_error = "Rate limited, the API is. Try again later, you must."
                continue

            post_res.raise_for_status()
            post_data = post_res.json()

            if not post_data.get("success"):
                logger.error(f"POST response: {post_data}")
                last_error = post_data.get("error_reason", "Unknown error")
                continue

            job_token = post_data["inference_job_token"]
            logger.info(f"Job token received: {job_token}")

            done = False
            result = None
            attempts = 0
            last_status = "unknown"
            no_progress_count = 0

            # Wait up to 60 seconds for the job to complete
            while not done and attempts < 30:
                time.sleep(2)
                attempts += 1

                try:
                    get_res = requests.get(
                        f"{GET_URL}{job_token}", headers=headers, timeout=10
                    )
                    get_res.raise_for_status()
                    get_data = get_res.json()

                    if not get_data.get("success"):
                        logger.error(f"Job status check failed: {get_data}")
                        break

                    state = get_data.get("state", {})
                    status_info = state.get("status", {})
                    status = status_info.get("status", "unknown")
                    attempt_count = status_info.get("attempt_count", 0)

                    logger.info(
                        f"Job status: {status} (attempt_count: {attempt_count}, poll: {attempts}/30)"
                    )

                    if status == "complete_success":
                        done = True
                        result = state.get("maybe_result")
                        break
                    elif status == "failed":
                        error_info = state.get(
                            "error",
                            status_info.get(
                                "maybe_extra_status_description", "Unknown error"
                            ),
                        )
                        logger.error(f"Job failed: {error_info}")
                        last_error = f"Failed with {model_name}: {error_info}"
                        break
                    elif status in ["started", "processing"]:
                        # Job is making progress
                        no_progress_count = 0
                        logger.info("Processing, the job is. Patient, we must be.")
                    elif status == "pending" and attempt_count == 0:
                        # Still in queue
                        no_progress_count += 1
                        if no_progress_count >= 10:  # 20 seconds of no progress
                            logger.warning(f"Job stuck in pending for {model_name}")
                            last_error = (
                                f"In queue too long with {model_name}, the job was."
                            )
                            break

                    last_status = status

                except Exception as e:
                    logger.error(f"Error checking job status: {e}")
                    break

            if (
                done
                and result
                and result.get("media_links")
                and result["media_links"].get("cdn_url")
            ):
                audio_url = result["media_links"]["cdn_url"]
                logger.info(f"Success! Downloading audio from: {audio_url}")

                try:
                    # Download the audio file
                    audio_res = requests.get(audio_url, timeout=30)
                    audio_res.raise_for_status()

                    # Save to temporary file
                    with tempfile.NamedTemporaryFile(
                        suffix=".wav", delete=False
                    ) as tmp_file:
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
                                        "text": f"Spoken with {model_name}, the words have been.\nAudio URL, you seek: {audio_url}",
                                    }
                                ]
                            }
                        else:
                            return {
                                "content": [
                                    {
                                        "type": "text",
                                        "text": f"Audio URL from {model_name}, you seek: {audio_url}\nBut play the sound, I could not. Download and play manually, you must.",
                                    }
                                ],
                                "isError": False,
                            }
                    finally:
                        # Clean up temporary file
                        try:
                            os.unlink(tmp_file_path)
                        except Exception as e:
                            logger.warning(f"Could not delete temporary file: {e}")

                except Exception as e:
                    logger.error(f"Error downloading/playing audio: {e}")
                    return {
                        "content": [
                            {
                                "type": "text",
                                "text": f"Generated audio URL with {model_name}: {audio_url}\nBut retrieve it, I could not. Error: {str(e)}",
                            }
                        ],
                        "isError": False,
                    }
            else:
                # This model didn't work, try the next one
                if not result:
                    last_error = (
                        f"No result from {model_name}. Status was: {last_status}"
                    )
                continue

        except requests.exceptions.RequestException as e:
            logger.error(f"Network error with {model_name}: {e}")
            last_error = f"Network error with {model_name}: {str(e)}"
            continue
        except Exception as e:
            logger.error(f"Error with {model_name}: {e}")
            last_error = f"Error with {model_name}: {str(e)}"
            continue

    # All models failed
    return {
        "content": [
            {
                "type": "text",
                "text": f"Failed, all voice models have. Patience with the Force, you must have.\n\nLast error: {last_error}\n\nBusy or down, the TTS service might be. Try again later, you should.",
            }
        ],
        "isError": True,
    }
