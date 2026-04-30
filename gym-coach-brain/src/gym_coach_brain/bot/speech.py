"""Speech-to-text transcription using OpenAI Whisper API."""
from __future__ import annotations

import os
from pathlib import Path
from typing import BinaryIO

from loguru import logger
from openai import AsyncOpenAI, OpenAIError


class WhisperTranscriber:
    """Async transcriber using OpenAI Whisper API."""

    def __init__(
        self,
        *,
        api_key: str | None = None,
        model: str = "whisper-1",
        language: str | None = None,
    ) -> None:
        """
        Initialize the Whisper transcriber.

        Args:
            api_key: OpenAI API key. If None, reads from OPENAI_API_KEY env var.
            model: Whisper model to use. Defaults to "whisper-1".
            language: ISO-639-1 language code (e.g., "en", "ru"). If None, auto-detects.
        """
        resolved_api_key = api_key or os.environ.get("OPENAI_API_KEY")
        if not resolved_api_key:
            raise ValueError("OpenAI API key is required for Whisper transcription")

        self.client = AsyncOpenAI(api_key=resolved_api_key)
        self.model = model
        self.language = language

    async def transcribe_file(
        self,
        audio_file: BinaryIO | Path | str,
        *,
        prompt: str | None = None,
    ) -> str:
        """
        Transcribe an audio file to text.

        Args:
            audio_file: Audio file path or file-like object.
                Supported formats: mp3, mp4, mpeg, mpga, m4a, wav, webm, ogg.
            prompt: Optional text to guide the model's style or continue a previous segment.

        Returns:
            Transcribed text.

        Raises:
            OpenAIError: If the API request fails.
            ValueError: If the file format is not supported.
        """
        try:
            # Prepare kwargs for the API call
            kwargs: dict[str, object] = {
                "model": self.model,
            }
            if self.language:
                kwargs["language"] = self.language
            if prompt:
                kwargs["prompt"] = prompt

            # Handle file path vs file object
            if isinstance(audio_file, (str, Path)):
                file_path = Path(audio_file)
                if not file_path.exists():
                    raise ValueError(f"Audio file not found: {file_path}")

                with open(file_path, "rb") as f:
                    transcript = await self.client.audio.transcriptions.create(
                        file=f,
                        **kwargs,  # type: ignore
                    )
            else:
                # File-like object
                transcript = await self.client.audio.transcriptions.create(
                    file=audio_file,
                    **kwargs,  # type: ignore
                )

            transcribed_text = transcript.text.strip()
            logger.info(
                "Transcribed audio ({} chars): {}...",
                len(transcribed_text),
                transcribed_text[:50],
            )
            return transcribed_text

        except OpenAIError as e:
            logger.error("Whisper API error: {}", e)
            raise
        except Exception as e:
            logger.error("Unexpected error during transcription: {}", e)
            raise

    async def transcribe_with_fallback(
        self,
        audio_file: BinaryIO | Path | str,
        *,
        prompt: str | None = None,
        fallback_message: str = "Не удалось распознать голосовое сообщение. Попробуй отправить текстом.",
    ) -> str:
        """
        Transcribe audio with automatic fallback on error.

        Args:
            audio_file: Audio file path or file-like object.
            prompt: Optional text to guide the model's style.
            fallback_message: Message to return if transcription fails.

        Returns:
            Transcribed text or fallback message.
        """
        try:
            return await self.transcribe_file(audio_file, prompt=prompt)
        except OpenAIError as e:
            logger.warning("Whisper API failed, returning fallback: {}", e)
            return fallback_message
        except Exception as e:
            logger.error("Transcription failed with unexpected error: {}", e)
            return fallback_message


async def download_telegram_voice(
    bot,
    file_id: str,
    destination: Path | str,
) -> Path:
    """
    Download a voice message from Telegram.

    Args:
        bot: Telegram bot instance with download_file method.
        file_id: Telegram file_id for the voice message.
        destination: Path where the file should be saved.

    Returns:
        Path to the downloaded file.

    Raises:
        Exception: If download fails.
    """
    try:
        dest_path = Path(destination)
        dest_path.parent.mkdir(parents=True, exist_ok=True)

        # Get file info from Telegram
        file = await bot.get_file(file_id)

        # Download the file
        await bot.download_file(file.file_path, dest_path)

        logger.debug("Downloaded voice message to {}", dest_path)
        return dest_path

    except Exception as e:
        logger.error("Failed to download voice message {}: {}", file_id, e)
        raise


def cleanup_audio_file(file_path: Path | str) -> None:
    """
    Delete a temporary audio file.

    Args:
        file_path: Path to the audio file to delete.
    """
    try:
        path = Path(file_path)
        if path.exists():
            path.unlink()
            logger.debug("Cleaned up audio file: {}", path)
    except Exception as e:
        logger.warning("Failed to cleanup audio file {}: {}", file_path, e)

# Made with Bob
