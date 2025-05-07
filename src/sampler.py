import requests
import uuid
import time
import os
import simpleaudio as sa
import io
import wave
import ffmpeg
import sys


def yoda_tts(text: str) -> dict:
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
        while not done and attempts < 10:
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
            print("Waited too long, I have. Cancelled, the job is.")
            return {"isError": True}
        if (
            result
            and result.get("media_links")
            and result["media_links"].get("cdn_url")
        ):
            audio_url = result["media_links"]["cdn_url"]
            # Download the audio file
            audio_res = requests.get(audio_url)
            # Save the audio file to 'samples' directory
            samples_dir = os.path.join(
                os.path.dirname(os.path.dirname(__file__)), "samples"
            )
            os.makedirs(samples_dir, exist_ok=True)
            filename = f"yoda_tts_{uuid.uuid4()}.wav"
            file_path = os.path.join(samples_dir, filename)
            with open(file_path, "wb") as f:
                f.write(audio_res.content)
            try:
                # Determine the next available number for the filename in 'samples' directory
                existing_files = [
                    f
                    for f in os.listdir(samples_dir)
                    if f.endswith(".wav") and f.split(".")[0].isdigit()
                ]
                if existing_files:
                    max_num = max([int(f.split(".")[0]) for f in existing_files])
                    next_num = max_num + 1
                else:
                    next_num = 1
                final_filename = f"{next_num}.wav"
                converted_path = os.path.join(samples_dir, final_filename)
                # Convert the audio file to mono, 22050 Hz, signed 16-bit PCM using ffmpeg
                try:
                    (
                        ffmpeg.input(file_path)
                        .output(converted_path, ac=1, ar=22050, sample_fmt="s16")
                        .overwrite_output()
                        .run(quiet=True)
                    )
                except Exception as ffmpeg_err:
                    print(
                        f"Audio saved at {file_path}, but ffmpeg conversion failed: {str(ffmpeg_err)}"
                    )
                    return {"isError": True}
                # Play the converted audio file using simpleaudio, from memory
                try:
                    with open(converted_path, "rb") as f:
                        audio_bytes = io.BytesIO(f.read())
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
                    print(
                        f"Converted audio at {converted_path}. Error playing sound: {str(play_err)}"
                    )
                    return {"isError": True}
                # Update transcript.txt with the filename and text
                transcript_path = os.path.join(samples_dir, "transcript.txt")
                with open(transcript_path, "a") as transcript_file:
                    transcript_file.write(f"samples/{final_filename}|{text}\n")
                print(
                    f"Audio URL: {audio_url}\nSaved: {file_path}\nConverted: {converted_path}"
                )
                return {"isError": False}
            finally:
                if os.path.exists(file_path):
                    os.remove(file_path)
        else:
            print("No audio URL found, there is.")
            return {"isError": True}
    except Exception as err:
        print(f"Error, there is: {str(err)}")
        return {"isError": True}


def main(text: str = None):
    if text is None:
        if len(sys.argv) > 1:
            text = " ".join(sys.argv[1:])
        else:
            text = input("Enter text for Yoda TTS: ")
    yoda_tts(text)


if __name__ == "__main__":
    main()
