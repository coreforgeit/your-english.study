import asyncio
import logging
import tempfile
from pathlib import Path
from typing import BinaryIO


logger = logging.getLogger(__name__)


class AudioSilenceTrimmer:
    async def trim(
        self,
        audio: bytes | BinaryIO,
        *,
        filename: str,
        content_type: str,
    ) -> tuple[str, bytes, str]:
        audio_bytes = self._read_audio_bytes(audio)
        trimmed_audio = await self._trim_with_ffmpeg(
            audio=audio_bytes,
            filename=filename,
        )
        return (filename, trimmed_audio, content_type)

    @staticmethod
    def _read_audio_bytes(audio: bytes | BinaryIO) -> bytes:
        if isinstance(audio, bytes):
            return audio

        current_position = None
        if audio.seekable():
            current_position = audio.tell()

        audio_bytes = audio.read()

        if current_position is not None:
            audio.seek(current_position)

        return audio_bytes

    async def _trim_with_ffmpeg(self, *, audio: bytes, filename: str) -> bytes:
        suffix = Path(filename).suffix or '.webm'

        with tempfile.TemporaryDirectory() as temp_dir:
            input_path = Path(temp_dir) / f'input{suffix}'
            output_path = Path(temp_dir) / f'output{suffix}'
            input_path.write_bytes(audio)

            process = await asyncio.create_subprocess_exec(
                'ffmpeg',
                '-hide_banner',
                '-loglevel',
                'error',
                '-y',
                '-i',
                str(input_path),
                '-af',
                (
                    'silenceremove='
                    'start_periods=1:'
                    'start_duration=0.2:'
                    'start_threshold=-45dB:'
                    'stop_periods=1:'
                    'stop_duration=0.6:'
                    'stop_threshold=-45dB'
                ),
                str(output_path),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            _, stderr = await process.communicate()

            if process.returncode != 0:
                logger.warning(
                    'FFmpeg silence trim failed, using original audio: %s',
                    stderr.decode(errors='replace').strip(),
                )
                return audio

            if not output_path.exists() or output_path.stat().st_size == 0:
                logger.warning('FFmpeg silence trim produced empty file, using original audio')
                return audio

            return output_path.read_bytes()
