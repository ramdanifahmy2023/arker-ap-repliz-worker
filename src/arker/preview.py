from __future__ import annotations

import json
from pathlib import Path
import shutil

from arker.adapters.media import Media, file_hashes, process


async def render_preview(output: Path) -> dict:
    output = Path(output).expanduser()
    if output.exists():
        raise ValueError("Gunakan folder preview baru agar bukti lama tidak tertimpa.")
    output.mkdir(parents=True, mode=0o700)
    source = output / "synthetic-source.mp4"
    await process(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i",
        "color=c=0x245c52:s=360x640:r=60:d=5,drawbox=x=20:y=320:w=100:h=180:color=orange:t=fill,drawbox=x=240:y=400:w=80:h=120:color=white:t=fill",
        "-f", "lavfi", "-i", "sine=frequency=440:sample_rate=48000:duration=5", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest", source])
    media = Media()
    before = await media.probe(source)
    frames = await media.frames(source, output, before)
    progress = []
    rendered = await media.render(source, output / "preview.mp4", "Lihat bedanya sebelum lewat", on_progress=lambda done, total: progress.append((done, total)))
    after = await media.probe(output / "preview.mp4")
    for stamp, name in ((2.9, "hook-visible.png"), (3.0, "hook-ended.png")):
        await process(["ffmpeg", "-v", "error", "-y", "-ss", str(stamp), "-i", output / "preview.mp4", "-frames:v", "1", output / name])
    from PIL import Image, ImageChops, ImageStat
    with Image.open(output / "hook-visible.png") as first, Image.open(output / "hook-ended.png") as second:
        region = (30, 70, 330, 220)
        difference = ImageStat.Stat(ImageChops.difference(first.crop(region), second.crop(region))).mean
        if sum(difference) < 5:
            raise RuntimeError("Hook belum terbukti terlihat sebelum detik 3 dan hilang pada detik 3.")
        # The asymmetric lower shapes detect accidental mirroring independently of text.
        left = second.getpixel((50, 400))
        right = second.getpixel((290, 450))
        if not (left[0] > left[2] + 80 and min(right[:3]) > 210):
            raise RuntimeError("Orientasi kiri/kanan hasil render tidak sesuai fixture.")
        zoom_edge = second.getpixel((10, 400))
        if zoom_edge[0] < zoom_edge[2] + 80:
            raise RuntimeError("Zoom 110% tidak sesuai tepi bentuk fixture.")
    from array import array
    audio = []
    for path in (source, output / "preview.mp4"):
        pcm = await process(["ffmpeg", "-v", "error", "-i", path, "-vn", "-ar", "8000", "-ac", "1", "-f", "f32le", "pipe:1"])
        samples = array("f")
        samples.frombytes(pcm)
        audio.append(samples)
    count = min(map(len, audio))
    correlation = sum(audio[0][i] * audio[1][i] for i in range(count)) / (sum(x*x for x in audio[0][:count]) * sum(x*x for x in audio[1][:count])) ** .5
    video = next(item for item in after["raw"]["streams"] if item["codec_type"] == "video")
    checks = {"h264": after["video_codec"] == "h264", "aac": after["audio_codec"] == "aac",
              "portrait_preserved": after["width"] == 360 and after["height"] == 640,
              "fps_30": video["r_frame_rate"] == "30/1", "hook_before_3_seconds": True,
              "source_not_mirrored": True, "frames": len(frames) == 6,
              "zoom_110_percent": True, "measured_progress": len(progress) > 0 and progress[-1][0] >= 4.9,
              "original_audio_preserved": correlation > .99 and abs(after["duration"] - before["duration"]) < .15}
    if not all(checks.values()):
        raise RuntimeError("Preview belum memenuhi pemeriksaan media.")
    from arker.db import Store
    from arker.ingest import intake
    from arker.worker import Worker
    class SyntheticDownloader:
        async def download(self, url, directory):
            path = Path(directory) / "source.mp4"
            shutil.copyfile(source, path)
            return {"path": str(path), "username": "fixture_source", "verified": True,
                    "description": "Video geometri buatan untuk pemeriksaan Arker.", "title": "Fixture lokal"}
    store = Store(output / "pipeline-runtime")
    accepted = intake(store, ["https://www.instagram.com/reel/ArkerFixture123/"])
    worker = Worker(store, downloader=SyntheticDownloader())
    for _ in range(4):
        await worker.tick()
    with store.connect() as db:
        asset = db.execute("SELECT * FROM assets WHERE id=?", (accepted["accepted"][0]["id"],)).fetchone()
        deliveries = db.execute("SELECT platform,state FROM deliveries").fetchall()
        checks["actual_worker_preview"] = asset["state"] == "preview_ready"
        checks["three_shadow_deliveries"] = len(deliveries) == 3 and all(item["state"] == "shadow" for item in deliveries)
        checks["source_credit"] = "source: @fixture_source" in (asset["caption"] or "")
        checks["no_outbound_attempt"] = db.execute("SELECT COUNT(*) FROM attempts").fetchone()[0] == 0
        checks["bank_and_six_frames"] = db.execute("SELECT COUNT(*) FROM artifacts WHERE kind='bank' OR kind LIKE 'frame-%'").fetchone()[0] == 7
    if not all(checks.values()):
        raise RuntimeError("Pipeline worker belum menyelesaikan preview lokal dan tiga delivery shadow.")
    result = {"passed": True, "synthetic": True, "published": False, "provider_calls": 0,
              "checks": checks, "output_sha256": rendered["sha256"], "source_sha256": file_hashes(source)["sha256"]}
    (output / "evidence.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    return result
