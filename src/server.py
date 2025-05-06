# server.py
from mcp.server.fastmcp import FastMCP
import requests
import uuid
import time
import re
import os
import simpleaudio as sa
import io
import wave

# Create an MCP server
mcp = FastMCP("Yoda TTS")


@mcp.tool()
def yodaTTS(text: str) -> dict:
    POST_URL = "https://api.fakeyou.com/tts/inference"
    GET_URL = "https://api.fakeyou.com/v1/model_inference/job_status/"
    post_body = {
        "uuid_idempotency_token": str(uuid.uuid4()),
        "tts_model_token": "weight_tqpbyrp6t9rmdez9c38zzvp0z",
        "inference_text": text,
    }
    try:
        post_res = requests.post(POST_URL, json=post_body)
        post_res.raise_for_status()
        post_data = post_res.json()
        if not post_data.get("success"):
            raise Exception("POST failed, it did.")
        job_token = post_data["inference_job_token"]
        done = False
        result = None
        attempts = 0
        while not done and attempts < 5:
            get_res = requests.get(f"{GET_URL}{job_token}")
            get_res.raise_for_status()
            get_data = get_res.json()
            if not get_data.get("success"):
                raise Exception("GET failed, it did.")
            status = get_data["state"]["status"]["status"]
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
            # Download the audio file
            audio_res = requests.get(audio_url)
            # Play the audio file using simpleaudio, from memory
            try:
                audio_bytes = io.BytesIO(audio_res.content)
                with wave.open(audio_bytes, "rb") as wav_file:
                    audio_data = wav_file.readframes(wav_file.getnframes())
                    num_channels = wav_file.getnchannels()
                    bytes_per_sample = wav_file.getsampwidth()
                    sample_rate = wav_file.getframerate()
                play_obj = sa.play_buffer(
                    audio_data, num_channels, bytes_per_sample, sample_rate
                )
                play_obj.wait_done()
            except Exception as play_err:
                return {
                    "content": [
                        {
                            "type": "text",
                            "text": f"Audio URL, you seek: {audio_url}\nBut error playing sound, there is: {str(play_err)}",
                        }
                    ],
                    "isError": True,
                }
            return {
                "content": [
                    {"type": "text", "text": f"Audio URL, you seek: {audio_url}"}
                ]
            }
        else:
            return {
                "content": [{"type": "text", "text": "No audio URL found, there is."}],
                "isError": True,
            }
    except Exception as err:
        return {
            "content": [{"type": "text", "text": f"Error, there is: {str(err)}"}],
            "isError": True,
        }
