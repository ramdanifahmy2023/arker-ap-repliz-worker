from __future__ import annotations

import asyncio
import hashlib
import json
import re
import sys
from pathlib import Path
from urllib.parse import urlparse

from . import AdapterError, Held


async def process(args, *, cwd=None, timeout=600, on_progress=None):
    try:
        child = await asyncio.create_subprocess_exec(*map(str, args), cwd=cwd, stdin=asyncio.subprocess.DEVNULL, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
    except (FileNotFoundError, PermissionError) as exc:
        raise Held('dependency_missing', 'Program pendukung belum tersedia atau tidak bisa dijalankan.') from exc
    async def capture():
        if on_progress is None:
            return await child.communicate()
        async def read_progress():
            collected = bytearray()
            while line := await child.stdout.readline():
                if len(collected) < 16 * 1024 * 1024:
                    collected.extend(line)
                if line.startswith(b'out_time_us='):
                    try:
                        value = int(line.split(b'=', 1)[1]) / 1_000_000
                    except ValueError:
                        continue
                    on_progress(max(0, value))
            return bytes(collected)
        output, errors = await asyncio.gather(read_progress(), child.stderr.read())
        await child.wait()
        return output, errors
    try:
        output, _errors = await asyncio.wait_for(capture(), timeout)
    except BaseException:
        if child.returncode is None:
            child.kill()
        await child.communicate()
        raise
    if child.returncode:
        raise AdapterError('media_command_failed', 'Proses media gagal. Periksa program, akses sumber, dan format video.')
    if len(output) > 16 * 1024 * 1024:
        raise AdapterError('media_output_limit', 'Metadata media melebihi batas ukuran.')
    return output


def file_hashes(path):
    digests = {name: hashlib.new(name) for name in ('md5', 'sha1', 'sha256')}
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            for digest in digests.values():
                digest.update(chunk)
    return {name: digest.hexdigest() for name, digest in digests.items()}


def local_file(path, directory):
    path, directory = Path(path), Path(directory).resolve()
    if path.is_symlink() or not path.is_file() or not path.resolve().is_relative_to(directory):
        raise Held('unsafe_media_path', 'File media harus berada di direktori kerja yang disetujui.')
    return path.resolve()


def instagram_url(url):
    parsed = urlparse(url)
    if parsed.scheme != 'https' or parsed.hostname not in {'instagram.com', 'www.instagram.com'} or parsed.username or parsed.password or parsed.port:
        raise Held('source_url', 'Gunakan tautan Reel Instagram HTTPS.')
    match = re.fullmatch(r'/(?:reel|reels|p)/([A-Za-z0-9_-]{3,100})/?', parsed.path)
    if not match:
        raise Held('source_url', 'Tautan harus menunjuk satu Reel atau posting Instagram.')
    return 'https://www.instagram.com/reel/' + match[1] + '/'


class Downloader:
    async def download(self, url, directory):
        canonical = instagram_url(url)
        directory = Path(directory).resolve()
        directory.mkdir(parents=True, exist_ok=True)
        await process([
            sys.executable, '-m', 'yt_dlp', '--ignore-config', '--no-playlist', '--no-progress',
            '--no-warnings', '--restrict-filenames', '--write-info-json', '--no-write-thumbnail',
            '--socket-timeout', '30', '--retries', '2', '--max-filesize', '1G',
            '--format', 'bv*[height<=1920]+ba/b[height<=1920]', '--merge-output-format', 'mp4',
            '--paths', directory, '--output', 'source.%(ext)s', '--', canonical,
        ], timeout=600)
        metadata_path = local_file(directory / 'source.info.json', directory)
        if metadata_path.stat().st_size > 16 * 1024 * 1024:
            raise Held('source_metadata', 'Metadata sumber terlalu besar.')
        info = json.loads(metadata_path.read_text('utf-8'))
        owner = info.get('uploader_id')
        if not isinstance(owner, str) or not re.fullmatch(r'[A-Za-z0-9_.]{1,30}', owner):
            raise Held('source_owner_unverified', 'Username pemilik sumber belum terverifikasi dari metadata.')
        if not str(info.get('extractor', '')).lower().startswith('instagram'):
            raise Held('source_owner_unverified', 'Metadata belum membuktikan sumber Instagram.')
        files = [path for path in directory.glob('source.*') if path.suffix.lower() in {'.mp4', '.mkv', '.webm', '.mov'}]
        if len(files) != 1:
            raise Held('source_file_missing', 'File video sumber belum lengkap.')
        path = local_file(files[0], directory)
        return {'path': str(path), 'username': owner, 'verified': True, 'description': str(info.get('description') or '')[:8000], 'title': str(info.get('title') or '')[:300], 'metadata_path': str(metadata_path)}


class Media:
    def __init__(self, config=None):
        self.config = config or {}
        self.ffmpeg = self.config.get('ffmpeg', 'ffmpeg')
        self.ffprobe = self.config.get('ffprobe', 'ffprobe')

    async def probe(self, path):
        raw = await process([self.ffprobe, '-v', 'error', '-show_format', '-show_streams', '-of', 'json', Path(path)], timeout=30)
        try:
            info = json.loads(raw)
            video = next(item for item in info['streams'] if item['codec_type'] == 'video')
            duration = float(info['format']['duration'])
            width, height = int(video['width']), int(video['height'])
            rotation = next((side.get('rotation', 0) for side in video.get('side_data_list', []) if 'rotation' in side), video.get('tags', {}).get('rotate', 0))
            if int(float(rotation)) % 180 == 90:
                width, height = height, width
        except (ValueError, KeyError, StopIteration, TypeError) as exc:
            raise Held('media_invalid', 'Video tidak mempunyai ukuran atau durasi yang valid.') from exc
        if width <= 0 or height <= 0 or width > 8192 or height > 8192 or not 0 < duration <= 3600:
            raise Held('media_invalid', 'Ukuran atau durasi video di luar batas.')
        return {'width': width, 'height': height, 'duration': duration, 'video_codec': video.get('codec_name'), 'audio_codec': next((s.get('codec_name') for s in info['streams'] if s.get('codec_type') == 'audio'), None), 'raw': info}

    async def frames(self, source, directory, info):
        result = []
        for number in range(6):
            path = Path(directory) / f'frame-{number + 1}.jpg'
            stamp = max(0, info['duration'] * (number + 0.5) / 6)
            await process([self.ffmpeg, '-v', 'error', '-y', '-ss', str(stamp), '-i', source, '-frames:v', '1', '-vf', 'scale=480:-2', path], timeout=60)
            result.append(str(path))
        return result

    async def transcribe(self, source, directory, settings):
        if not settings.get('transcription_enabled'):
            return {'text': '', 'status': 'disabled'}
        model = Path(settings.get('whisper_model', '')).expanduser()
        if not model.is_file() or model.is_symlink():
            raise Held('transcript_model_missing', 'Model whisper.cpp belum tersedia di mesin worker.')
        info = await self.probe(source)
        if not info['audio_codec']:
            return {'text': '', 'status': 'no_audio'}
        directory = Path(directory)
        audio, transcript = directory / 'transcript-audio.wav', directory / 'transcript'
        await process([self.ffmpeg, '-v', 'error', '-y', '-i', source, '-vn', '-ar', '16000', '-ac', '1', '-c:a', 'pcm_s16le', audio], timeout=90)
        await process([settings.get('whisper_executable', 'whisper-cli'), '-m', model, '-f', audio, '-l', 'auto', '-otxt', '-of', transcript], timeout=600)
        path = local_file(transcript.with_suffix('.txt'), directory)
        if path.stat().st_size > 1024 * 1024:
            raise Held('transcript_size', 'Transkrip melebihi batas ukuran.')
        return {'text': path.read_text('utf-8').strip(), 'path': str(path), 'status': 'transcribed'}

    @staticmethod
    def overlay(hook, width, height, path):
        from functools import lru_cache
        from PIL import Image, ImageDraw, ImageFont

        font_path = Path(__file__).resolve().parents[1] / 'assets' / 'fonts' / 'BarlowSemiCondensed-Bold.ttf'
        if not font_path.is_file():
            raise Held('font_missing', 'Font hook belum tersedia.')
        hook = ' '.join(str(hook).split())
        if not hook or len(hook) > 160:
            raise Held('hook_invalid', 'Hook harus berisi 1 sampai 160 karakter.')
        if width < 160 or height < 120:
            raise Held('hook_dimensions', 'Resolusi video terlalu kecil untuk hook yang terbaca.')
        canvas = Image.new('RGBA', (width, height), (0, 0, 0, 0))
        draw = ImageDraw.Draw(canvas)
        words = hook.split()
        target_size = round(min(width * .084, height * .106))
        normal_minimum = max(12, round(target_size * .73))
        legacy_minimum = max(12, round(min(width * .045, height * .06)))
        safe_inset = max(8, round(width * .07))

        def balanced_lines(font, stroke, maximum_width, line_limit):
            @lru_cache(maxsize=None)
            def measured(start, end):
                text = ' '.join(words[start:end])
                bounds = draw.textbbox((0, 0), text, font=font, anchor='ms', stroke_width=stroke)
                return text, bounds[2] - bounds[0]

            def partitions(start, remaining):
                if remaining == 1:
                    text, measured_width = measured(start, len(words))
                    if measured_width <= maximum_width:
                        yield [(text, measured_width)]
                    return
                for end in range(start + 1, len(words) - remaining + 2):
                    text, measured_width = measured(start, end)
                    if measured_width > maximum_width:
                        break
                    for rest in partitions(end, remaining - 1):
                        yield [(text, measured_width), *rest]

            for count in range(1, min(line_limit, len(words)) + 1):
                best, best_score = None, float('inf')
                for candidate in partitions(0, count):
                    widths = [item[1] for item in candidate]
                    score = (max(widths) - min(widths)) ** 2
                    if len(words) >= count * 3:
                        score += sum(maximum_width ** 2 for text, _ in candidate if ' ' not in text)
                    if score < best_score:
                        best, best_score = [item[0] for item in candidate], score
                if best:
                    return best
            return None

        # New hooks stay large and within two lines; older text may use a bounded third line.
        passes = [(2, normal_minimum)]
        if len(hook) > 68:
            passes.append((3, legacy_minimum))
        lines = None
        for line_limit, minimum in passes:
            for size in range(target_size, minimum - 1, -1):
                font = ImageFont.truetype(str(font_path), size)
                stroke = max(1, round(size * .025))
                padding_x = max(4, round(size * .30))
                maximum_width = width - 2 * (safe_inset + padding_x)
                lines = balanced_lines(font, stroke, maximum_width, line_limit)
                if lines:
                    break
            if lines:
                break
        if not lines:
            raise Held('hook_too_wide', 'Hook terlalu panjang untuk tetap terbaca. Pendekkan kalimat atau kata yang panjang.')

        bounds = [draw.textbbox((0, 0), line, font=font, anchor='ms', stroke_width=stroke) for line in lines]
        glyph_top = min(box[1] for box in bounds)
        glyph_bottom = max(box[3] for box in bounds)
        gap = max(3, round(size * .20))
        line_height = glyph_bottom - glyph_top + gap
        text_top = round(height * .16)
        padding_y = max(3, round(size * .22))
        positions = [(width // 2, text_top - glyph_top + index * line_height) for index in range(len(lines))]
        text_bounds = [list(draw.textbbox(position, line, font=font, anchor='ms', stroke_width=stroke)) for position, line in zip(positions, lines)]
        backing_bounds = [
            min(box[0] for box in text_bounds) - padding_x,
            min(box[1] for box in text_bounds) - padding_y,
            max(box[2] for box in text_bounds) + padding_x,
            max(box[3] for box in text_bounds) + padding_y,
        ]
        draw.rounded_rectangle(backing_bounds, radius=max(2, round(size * .12)), fill=(16, 20, 24, 194))
        for position, line in zip(positions, lines):
            draw.text(position, line, font=font, fill='white', anchor='ms', stroke_width=stroke, stroke_fill=(12, 16, 20, 255))
        canvas.save(path)
        return {
            'style_id': 'barlow-compact-v2', 'lines': lines, 'line_count': len(lines),
            'font_size': size, 'max_width': maximum_width, 'text_bounds': text_bounds,
            'backing_bounds': backing_bounds, 'safe_inset': safe_inset,
            'legacy_fallback': line_limit == 3,
        }

    async def render(self, source, destination, hook, *, on_progress=None):
        info = await self.probe(source)
        if not self.config.get('min_duration', 3) <= info['duration'] <= self.config.get('max_duration', 90):
            raise Held('media_duration', 'Durasi video tidak memenuhi batas pengolahan.')
        destination = Path(destination)
        destination.parent.mkdir(parents=True, exist_ok=True)
        width, height = info['width'] // 2 * 2, info['height'] // 2 * 2
        # Bounded portrait/landscape dimensions preserve orientation and avoid unbounded render cost.
        factor = min(1, 1920 / max(width, height))
        width, height = int(width * factor) // 2 * 2, int(height * factor) // 2 * 2
        overlay = destination.parent / 'hook-overlay.png'
        layout = self.overlay(hook, width, height, overlay)
        zoom_w, zoom_h = int(width * 1.1) // 2 * 2, int(height * 1.1) // 2 * 2
        filters = f'[0:v]setpts=PTS-STARTPTS,fps=30,scale={zoom_w}:{zoom_h},crop={width}:{height},setsar=1[base];[base][1:v]overlay=0:0:enable=\'lt(t,3)\',format=yuv420p[out]'
        await process([self.ffmpeg, '-v', 'error', '-y', '-progress', 'pipe:1', '-nostats', '-i', source, '-i', overlay,
                       '-filter_complex', filters, '-map', '[out]', '-map', '0:a?', '-c:v', 'libx264',
                       '-preset', 'medium', '-crf', '20', '-c:a', 'aac', '-b:a', '192k', '-ar', '48000',
                       '-map_metadata', '-1', '-metadata', 'title=' + hook, '-metadata', 'comment=Arker render',
                       '-movflags', '+faststart', '-t', str(info['duration']), destination], timeout=1200, on_progress=(lambda elapsed: on_progress(min(info['duration'], elapsed), info['duration'])) if on_progress else None)
        result = await self.probe(destination)
        if result['video_codec'] != 'h264' or (info['audio_codec'] and result['audio_codec'] != 'aac'):
            raise Held('render_codec', 'Hasil render belum memenuhi H.264/AAC.')
        return {'path': str(destination), 'sha256': file_hashes(destination)['sha256'], 'size': destination.stat().st_size, 'duration': result['duration'], 'layout': layout}
