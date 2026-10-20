"""Render synthetic hook samples locally; no provider, source media, or publication."""
from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFont, ImageStat

from arker.adapters.media import Media, process


async def preview(output: Path):
    if output.exists():
        raise ValueError('Pilih direktori bukti baru; preview tidak menimpa hasil lama.')
    output.mkdir(parents=True)
    font_path = Path(__file__).resolve().parents[1] / 'src/arker/assets/fonts/BarlowSemiCondensed-Bold.ttf'
    label_font = ImageFont.truetype(str(font_path), 22)
    results = []
    sheet = Image.new('RGB', (1160, 800), '#e9ece5')
    sheet_draw = ImageDraw.Draw(sheet)
    sheet_draw.text((20, 16), 'FIXTURE SINTETIS | barlow-compact-v2 | lebar tampilan 360 px', font=label_font, fill='#17211b')
    for column, (name, width, height) in enumerate([('portrait', 720, 1280), ('square', 720, 720), ('landscape', 1280, 720)]):
        directory = output / name
        directory.mkdir()
        background = Image.new('RGB', (width, height), '#e9e9dd')
        drawing = ImageDraw.Draw(background)
        for index in range(8):
            drawing.rectangle((index * width // 8, 0, (index + 1) * width // 8, height // 2), fill='#f9f9f1' if index % 2 else '#344949')
        drawing.ellipse((width * .07, height * .55, width * .44, height * .91), fill='#da7649')
        drawing.rectangle((width * .58, height * .56, width * .94, height * .94), fill='#698e80')
        drawing.text((width * .08, height * .94), 'FIXTURE: bentuk dan warna buatan', font=label_font, fill='#18221c')
        background.save(directory / 'background.png')
        media = Media()
        await process([media.ffmpeg, '-v', 'error', '-y', '-loop', '1', '-framerate', '60', '-i', directory / 'background.png', '-f', 'lavfi', '-i', 'sine=frequency=440:sample_rate=48000', '-t', '5', '-c:v', 'libx264', '-preset', 'fast', '-pix_fmt', 'yuv420p', '-c:a', 'aac', directory / 'source.mp4'])
        rendered = await media.render(directory / 'source.mp4', directory / 'render.mp4', 'Kucingnya malah ikut duduk di kursi')
        await process([media.ffmpeg, '-v', 'error', '-i', directory / 'render.mp4', '-vf', "select='eq(n,0)+eq(n,89)+eq(n,90)+eq(n,120)'", '-fps_mode', 'vfr', directory / 'frame-%02d.png'])
        frames = [Image.open(directory / f'frame-{index:02d}.png').convert('RGB') for index in range(1, 5)]
        region = tuple(rendered['layout']['backing_bounds'])
        difference = lambda image: sum(ImageStat.Stat(ImageChops.difference(image.crop(region), frames[3].crop(region))).mean) / 3
        deltas = [difference(frame) for frame in frames[:3]]
        checks = {'hook_at_frame_0': deltas[0] > 5, 'hook_at_frame_89': deltas[1] > 5, 'no_hook_at_frame_90': deltas[2] < 1.5}
        if not all(checks.values()):
            raise AssertionError(f'{name}: pemeriksaan frame gagal {checks}')
        x = 20 + column * 380
        sheet_draw.text((x, 56), f'{name} {width} × {height}', font=label_font, fill='#17211b')
        thumbnail = frames[0].resize((360, round(height * 360 / width)), Image.Resampling.LANCZOS)
        sheet.paste(thumbnail, (x, 90))
        sheet_draw.text((x, 100 + thumbnail.height), f"{rendered['layout']['line_count']} baris / {rendered['layout']['font_size']} px sumber", font=label_font, fill='#17211b')
        results.append({'shape': name, 'layout': rendered['layout'], 'checks': checks, 'region_mean_delta_to_frame_120': deltas})
        for frame in frames:
            frame.close()
    sheet.save(output / 'contact-sheet.png')
    (output / 'report.json').write_text(json.dumps({'fixture': True, 'network': False, 'publication': False, 'samples': results}, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'samples': len(results), 'checks_passed': sum(sum(item['checks'].values()) for item in results), 'publication': False}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    asyncio.run(preview(args.output.resolve()))
