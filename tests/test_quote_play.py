import json
import os
import sys
import tempfile
import time
from unittest.mock import MagicMock, Mock, patch

import pytest
import requests
import responses

# Add the src directory to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from tools.quote_play import (
    play_audio,
    play_audio_pygame,
    play_audio_simpleaudio,
    play_audio_system,
    quote_play,
)


class TestAudioPlayback:
    """Test individual audio playback functions"""

    def test_play_audio_pygame_success(self, tmp_path):
        """Test pygame audio playback when successful"""
        # Create a dummy audio file
        audio_file = tmp_path / "test.wav"
        audio_file.write_bytes(b"dummy audio content")

        with patch("tools.quote_play.PYGAME_AVAILABLE", True):
            with patch("tools.quote_play.pygame.mixer.music.load") as mock_load:
                with patch("tools.quote_play.pygame.mixer.music.play") as mock_play:
                    with patch(
                        "tools.quote_play.pygame.mixer.music.get_busy",
                        side_effect=[True, True, False],
                    ):
                        result = play_audio_pygame(str(audio_file))
                        assert result is True
                        mock_load.assert_called_once_with(str(audio_file))
                        mock_play.assert_called_once()

    def test_play_audio_pygame_failure(self, tmp_path):
        """Test pygame audio playback when it fails"""
        audio_file = tmp_path / "test.wav"
        audio_file.write_bytes(b"dummy audio content")

        with patch("tools.quote_play.PYGAME_AVAILABLE", True):
            with patch(
                "tools.quote_play.pygame.mixer.music.load",
                side_effect=Exception("Load failed"),
            ):
                result = play_audio_pygame(str(audio_file))
                assert result is False

    def test_play_audio_simpleaudio_success(self, tmp_path):
        """Test simpleaudio playback when successful"""
        audio_file = tmp_path / "test.wav"
        # Create a minimal WAV file header
        wav_header = (
            b"RIFF" + b"\x00" * 4 + b"WAVEfmt " + b"\x00" * 16 + b"data" + b"\x00" * 4
        )
        audio_file.write_bytes(wav_header)

        mock_wave_obj = Mock()
        mock_play_obj = Mock()
        mock_wave_obj.play.return_value = mock_play_obj

        with patch(
            "tools.quote_play.sa.WaveObject.from_wave_file", return_value=mock_wave_obj
        ):
            result = play_audio_simpleaudio(str(audio_file))
            assert result is True
            mock_wave_obj.play.assert_called_once()
            mock_play_obj.wait_done.assert_called_once()

    def test_play_audio_simpleaudio_failure(self, tmp_path):
        """Test simpleaudio playback when it fails"""
        audio_file = tmp_path / "test.wav"
        audio_file.write_bytes(b"dummy audio content")

        with patch(
            "tools.quote_play.sa.WaveObject.from_wave_file",
            side_effect=Exception("Failed to load"),
        ):
            result = play_audio_simpleaudio(str(audio_file))
            assert result is False

    @pytest.mark.parametrize(
        "platform,expected_cmd",
        [
            ("darwin", ["afplay"]),
            ("linux", ["aplay"]),  # First command that would be tried
            ("win32", ["powershell"]),
        ],
    )
    def test_play_audio_system_success(self, tmp_path, platform, expected_cmd):
        """Test system audio playback on different platforms"""
        audio_file = tmp_path / "test.wav"
        audio_file.write_bytes(b"dummy audio content")

        with patch("sys.platform", platform):
            with patch("subprocess.run") as mock_run:
                result = play_audio_system(str(audio_file))
                assert result is True
                # Check that the expected command was called
                assert any(
                    expected_cmd[0] in str(call) for call in mock_run.call_args_list
                )

    def test_play_audio_fallback_chain(self, tmp_path):
        """Test that play_audio tries multiple methods in order"""
        audio_file = tmp_path / "test.wav"
        audio_file.write_bytes(b"dummy audio content")

        with patch("tools.quote_play.PYGAME_AVAILABLE", True):
            with patch(
                "tools.quote_play.play_audio_pygame", return_value=False
            ) as mock_pygame:
                with patch(
                    "tools.quote_play.play_audio_simpleaudio", return_value=False
                ) as mock_simple:
                    with patch(
                        "tools.quote_play.play_audio_system", return_value=True
                    ) as mock_system:
                        result = play_audio(str(audio_file))
                        assert result is True
                        mock_pygame.assert_called_once()
                        mock_simple.assert_called_once()
                        mock_system.assert_called_once()


class TestQuotePlay:
    """Test the main quote_play function"""

    @responses.activate
    def test_successful_tts_generation(self):
        """Test successful TTS generation and playback"""
        # Mock the initial POST request
        job_token = "test-job-token"
        responses.add(
            responses.POST,
            "https://api.fakeyou.com/tts/inference",
            json={"success": True, "inference_job_token": job_token},
            status=200,
        )

        # Mock the status polling - first pending, then complete
        responses.add(
            responses.GET,
            f"https://api.fakeyou.com/v1/model_inference/job_status/{job_token}",
            json={"success": True, "state": {"status": {"status": "pending"}}},
            status=200,
        )

        audio_url = "https://example.com/audio.wav"
        responses.add(
            responses.GET,
            f"https://api.fakeyou.com/v1/model_inference/job_status/{job_token}",
            json={
                "success": True,
                "state": {
                    "status": {"status": "complete_success"},
                    "maybe_result": {"media_links": {"cdn_url": audio_url}},
                },
            },
            status=200,
        )

        # Mock the audio download
        responses.add(responses.GET, audio_url, body=b"fake audio data", status=200)

        # Mock audio playback
        with patch("tools.quote_play.play_audio", return_value=True):
            result = quote_play("Test quote")

        assert result["content"][0]["type"] == "text"
        assert "Spoken with" in result["content"][0]["text"]
        assert "the words have been" in result["content"][0]["text"]
        assert audio_url in result["content"][0]["text"]
        assert "isError" not in result

    @responses.activate
    def test_api_post_failure(self):
        """Test when the initial POST request fails"""
        responses.add(
            responses.POST,
            "https://api.fakeyou.com/tts/inference",
            json={"success": False, "error": "Invalid model"},
            status=200,
        )

        result = quote_play("Test quote")

        assert result["isError"] is True
        assert "Failed, all voice models have" in result["content"][0]["text"]

    @responses.activate
    def test_job_timeout(self):
        """Test when job stays in pending status and times out"""
        job_token = "test-job-token"
        responses.add(
            responses.POST,
            "https://api.fakeyou.com/tts/inference",
            json={"success": True, "inference_job_token": job_token},
            status=200,
        )

        # Mock all status checks to return pending
        for _ in range(15):  # More than the 10 attempts
            responses.add(
                responses.GET,
                f"https://api.fakeyou.com/v1/model_inference/job_status/{job_token}",
                json={"success": True, "state": {"status": {"status": "pending"}}},
                status=200,
            )

        with patch("time.sleep"):  # Speed up test
            result = quote_play("Test quote")

        assert result["isError"] is True
        assert "Failed, all voice models have" in result["content"][0]["text"]

    @responses.activate
    def test_job_failed_status(self):
        """Test when job returns failed status"""
        job_token = "test-job-token"
        responses.add(
            responses.POST,
            "https://api.fakeyou.com/tts/inference",
            json={"success": True, "inference_job_token": job_token},
            status=200,
        )

        responses.add(
            responses.GET,
            f"https://api.fakeyou.com/v1/model_inference/job_status/{job_token}",
            json={
                "success": True,
                "state": {
                    "status": {"status": "failed"},
                    "error": "TTS generation failed",
                },
            },
            status=200,
        )

        result = quote_play("Test quote")

        assert result["isError"] is True
        assert "Failed, all voice models have" in result["content"][0]["text"]

    @responses.activate
    def test_audio_playback_failure(self):
        """Test when audio download succeeds but playback fails"""
        job_token = "test-job-token"
        audio_url = "https://example.com/audio.wav"

        responses.add(
            responses.POST,
            "https://api.fakeyou.com/tts/inference",
            json={"success": True, "inference_job_token": job_token},
            status=200,
        )

        responses.add(
            responses.GET,
            f"https://api.fakeyou.com/v1/model_inference/job_status/{job_token}",
            json={
                "success": True,
                "state": {
                    "status": {"status": "complete_success"},
                    "maybe_result": {"media_links": {"cdn_url": audio_url}},
                },
            },
            status=200,
        )

        responses.add(responses.GET, audio_url, body=b"fake audio data", status=200)

        # Mock audio playback failure
        with patch("tools.quote_play.play_audio", return_value=False):
            result = quote_play("Test quote")

        assert "isError" not in result or result["isError"] is False
        assert audio_url in result["content"][0]["text"]
        assert "play the sound, I could not" in result["content"][0]["text"]

    @responses.activate
    def test_network_error_handling(self):
        """Test handling of network errors"""
        responses.add(
            responses.POST,
            "https://api.fakeyou.com/tts/inference",
            body=requests.exceptions.ConnectionError("Network error"),
        )

        result = quote_play("Test quote")

        assert result["isError"] is True
        assert "Failed, all voice models have" in result["content"][0]["text"]
        assert "Network error" in result["content"][0]["text"]

    @responses.activate
    def test_missing_audio_url(self):
        """Test when job completes but no audio URL is provided"""
        job_token = "test-job-token"

        responses.add(
            responses.POST,
            "https://api.fakeyou.com/tts/inference",
            json={"success": True, "inference_job_token": job_token},
            status=200,
        )

        responses.add(
            responses.GET,
            f"https://api.fakeyou.com/v1/model_inference/job_status/{job_token}",
            json={
                "success": True,
                "state": {
                    "status": {"status": "complete_success"},
                    "maybe_result": {},  # No media_links
                },
            },
            status=200,
        )

        result = quote_play("Test quote")

        assert result["isError"] is True
        assert "Failed, all voice models have" in result["content"][0]["text"]
        assert "No result from" in result["content"][0]["text"]


@pytest.mark.integration
class TestIntegration:
    """Integration tests that actually call the API (use sparingly)"""

    @pytest.mark.skip(reason="Requires actual API access")
    def test_real_api_call(self):
        """Test with actual FakeYou API - only run manually"""
        # This test is skipped by default to avoid hitting the API in CI
        result = quote_play("Test, this is.")
        print(f"Result: {json.dumps(result, indent=2)}")
        assert "content" in result


if __name__ == "__main__":
    # Run just the integration test manually:
    # python -m pytest tests/test_quote_play.py::TestIntegration::test_real_api_call -s -m integration
    pytest.main([__file__, "-v"])
