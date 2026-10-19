import asyncio
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch

import httpx

from arker.adapters import AdapterError, Held
from arker.adapters.ai import AI
from arker.adapters.drive import Drive, folder_id
from arker.adapters.media import Media, instagram_url
from arker.adapters.repliz import Repliz, schedule_evidence


class ReplizTests(unittest.IsolatedAsyncioTestCase):
    async def test_complete_pagination_and_partial_rejected(self):
        responses = [
            {'docs': [{'id': 'first'}], 'totalDocs': 2, 'page': 1, 'hasNextPage': True},
            {'docs': [{'id': 'second'}], 'totalDocs': 2, 'page': 2, 'hasNextPage': False},
        ]
        def handler(request):
            self.assertEqual(request.url.host, 'api.repliz.com')
            self.assertTrue(request.headers['authorization'].startswith('Basic '))
            return httpx.Response(200, json=responses.pop(0))
        client = Repliz({'access_key': 'fixture-A', 'secret_key': 'fixture-B'}, transport=httpx.MockTransport(handler), interval=0)
        self.assertEqual(len(await client.accounts()), 2)
        await client.close()
        client = Repliz({'access_key': 'fixture', 'secret_key': 'fixture'}, transport=httpx.MockTransport(lambda r: httpx.Response(200, json={'docs': [], 'totalDocs': 2, 'page': 1, 'hasNextPage': False})), interval=0)
        with self.assertRaises(Held):
            await client.accounts()
        await client.close()

    async def test_timeout_mutation_ambiguous_never_retried(self):
        calls = []
        def handler(request):
            calls.append(request)
            raise httpx.ReadTimeout('sensitive body fixture-B', request=request)
        client = Repliz({'access_key': 'fixture', 'secret_key': 'fixture-B'}, transport=httpx.MockTransport(handler), interval=0)
        with self.assertRaises(AdapterError) as caught:
            await client.create_schedule({'fixture': True})
        self.assertTrue(caught.exception.ambiguous)
        self.assertNotIn('fixture-B', str(caught.exception))
        self.assertEqual(len(calls), 1)
        await client.close()

    async def test_reply_uses_documented_contract(self):
        def handler(request):
            self.assertEqual(request.method, 'POST')
            self.assertEqual(request.url.path, '/public/comment/comment-one')
            self.assertEqual(json.loads(request.content), {'text': 'Konteks fixture'})
            return httpx.Response(200, json={'commentId': 'remote-reply'})
        client = Repliz({'access_key': 'fixture', 'secret_key': 'fixture'}, transport=httpx.MockTransport(handler), interval=0)
        self.assertEqual(await client.reply('comment-one', 'Konteks fixture'), 'remote-reply')
        await client.close()

    def test_published_requires_matching_identity_and_post_link(self):
        base = {'id': 'one', 'accountId': 'account', 'status': 'success'}
        with self.assertRaises(Held):
            schedule_evidence(base, 'one', 'account', 'youtube')
        with self.assertRaises(Held):
            schedule_evidence({**base, 'url': 'https://youtube.com/shorts/video'}, 'wrong', 'account', 'youtube')
        with self.assertRaises(Held):
            schedule_evidence({**base, 'url': 'https://youtube.com.attacker.invalid/shorts/video'}, 'one', 'account', 'youtube')
        self.assertEqual(schedule_evidence({**base, 'url': 'https://youtube.com/shorts/video'}, 'one', 'account', 'youtube')['state'], 'published')
        self.assertEqual(schedule_evidence({**base, 'status': 'error'}, 'one', 'account', 'youtube')['state'], 'failed')


class DriveTests(unittest.IsolatedAsyncioTestCase):
    async def test_full_checksums_identity_and_public_permission_required(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'fixture.mp4'
            payload = b'fixture video bytes'
            path.write_bytes(payload)
            item = {'id': 'filefixture12345', 'parents': ['folderfixture12345'], 'size': str(len(payload)), 'permissions': [{'type': 'anyone', 'role': 'reader'}], **{algo + 'Checksum': hashlib.new(algo, payload).hexdigest() for algo in ('md5', 'sha1', 'sha256')}}
            def handler(request):
                self.assertEqual(request.method, 'GET')
                return httpx.Response(200, json={'files': [item]})
            drive = Drive({'access_token': 'fixture'}, transport=httpx.MockTransport(handler))
            result = await drive.verify(path, 'https://drive.google.com/drive/folders/folderfixture12345')
            self.assertEqual(result['sha256'], hashlib.sha256(payload).hexdigest())
            item['sha1Checksum'] = '0' * 40
            with self.assertRaises(Held):
                await drive.verify(path, 'https://drive.google.com/drive/folders/folderfixture12345')
            item['sha1Checksum'] = hashlib.sha1(payload).hexdigest()
            item['permissions'] = []
            with self.assertRaises(Held):
                await drive.verify(path, 'https://drive.google.com/drive/folders/folderfixture12345')
            await drive.close()

    def test_folder_url_does_not_accept_arbitrary_hosts(self):
        for url in ['https://evil.invalid/drive/folders/folderfixture12345', 'http://drive.google.com/drive/folders/folderfixture12345', 'https://drive.google.com/file/d/filefixture12345']:
            with self.assertRaises(Held):
                folder_id(url)


class MediaTests(unittest.IsolatedAsyncioTestCase):
    async def test_disabled_ai_uses_source_context_without_network(self):
        result = await AI({'enabled': False}, {}).draft({'description': 'Keterangan sumber fixture'})
        self.assertFalse(result['ai_used'])
        self.assertEqual(result['caption'], 'Keterangan sumber fixture')

    def test_instagram_source_restricted_and_canonical(self):
        self.assertEqual(instagram_url('https://instagram.com/p/Fixture123/?utm_source=test'), 'https://www.instagram.com/reel/Fixture123/')
        for url in ['http://instagram.com/reel/Fixture123', 'https://instagram.com.attacker.invalid/reel/Fixture123/', 'https://instagram.com/accounts/login/', 'file:///private/video.mp4']:
            with self.assertRaises(Held):
                instagram_url(url)

    def test_hook_is_measured_and_bounded(self):
        with tempfile.TemporaryDirectory() as temp:
            result = Media.overlay('Lihat gerakan kecil di bagian ini', 360, 640, Path(temp) / 'overlay.png')
            self.assertLessEqual(len(result['lines']), 3)
            self.assertTrue((Path(temp) / 'overlay.png').is_file())
            with self.assertRaises(Held):
                Media.overlay('X' * 161, 360, 640, Path(temp) / 'bad.png')

    async def test_fps_precedes_hook_and_no_mirror(self):
        with tempfile.TemporaryDirectory() as temp:
            source, output = Path(temp) / 'source.mp4', Path(temp) / 'render.mp4'
            source.write_bytes(b'fixture')
            output.write_bytes(b'fixture-output')
            media = Media()
            media.probe = AsyncMock(side_effect=[{'width': 360, 'height': 640, 'duration': 4, 'audio_codec': 'aac'}, {'duration': 4, 'video_codec': 'h264', 'audio_codec': 'aac'}])
            with patch('arker.adapters.media.process', new_callable=AsyncMock) as command:
                await media.render(source, output, 'Hook fixture')
            arguments = command.call_args.args[0]
            filters = arguments[arguments.index('-filter_complex') + 1]
            self.assertLess(filters.index('fps=30'), filters.index('overlay='))
            self.assertIn("lt(t,3)", filters)
            self.assertNotIn('hflip', filters)
            self.assertIn('scale=396:704', filters)
            self.assertEqual(arguments[arguments.index('-map_metadata') + 1], '-1')

    async def test_display_rotation_preserves_portrait(self):
        info = {'streams': [{'codec_type': 'video', 'codec_name': 'h264', 'width': 640, 'height': 360, 'side_data_list': [{'rotation': -90}]}], 'format': {'duration': '4'}}
        with patch('arker.adapters.media.process', new=AsyncMock(return_value=json.dumps(info).encode())):
            result = await Media().probe('fixture.mp4')
        self.assertEqual((result['width'], result['height']), (360, 640))

    async def test_transcription_uses_local_wav_and_model(self):
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp)
            model = directory / 'model.bin'
            model.write_bytes(b'fixture model')
            media = Media()
            media.probe = AsyncMock(return_value={'audio_codec': 'aac'})
            commands = []
            async def run(arguments, **kwargs):
                commands.append(arguments)
                if '-otxt' in arguments:
                    (directory / 'transcript.txt').write_text('Kalimat fixture dari audio.', encoding='utf-8')
                return b''
            with patch('arker.adapters.media.process', new=run):
                result = await media.transcribe(directory / 'source.mp4', directory, {'transcription_enabled': True, 'whisper_model': str(model), 'whisper_executable': 'whisper-cli'})
            self.assertEqual(result['status'], 'transcribed')
            self.assertEqual(result['text'], 'Kalimat fixture dari audio.')
            self.assertIn('16000', commands[0])
            self.assertIn(model, commands[1])
            self.assertFalse(any('http' in str(item) for command in commands for item in command))

    async def test_process_reports_measured_encoder_time(self):
        import sys
        from arker.adapters.media import process
        observed = []
        output = await process([sys.executable, '-c', "print('out_time_us=500000');print('out_time_us=1500000');print('progress=end')"], timeout=10, on_progress=observed.append)
        self.assertEqual(observed, [.5, 1.5])
        self.assertIn(b'progress=end', output)
