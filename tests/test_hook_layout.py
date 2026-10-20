import tempfile
import unittest
from pathlib import Path

from PIL import Image

from arker.adapters import Held
from arker.adapters.media import Media


class HookLayoutTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.output = Path(self.directory.name) / 'hook.png'

    def overlay(self, text, width=360, height=640):
        return Media.overlay(text, width, height, self.output)

    def test_short_hook_is_larger_balanced_two_lines_in_all_orientations(self):
        for width, height in [(360, 640), (720, 1280), (720, 720), (1280, 720), (1080, 1920)]:
            with self.subTest(size=(width, height)):
                result = self.overlay('Kucingnya malah ikut duduk di kursi', width, height)
                self.assertEqual(result['style_id'], 'barlow-compact-v2')
                self.assertEqual(result['line_count'], 2)
                self.assertFalse(result['legacy_fallback'])
                self.assertGreaterEqual(result['font_size'], round(min(width * .067, height * .084)))
                self.assertEqual(' '.join(result['lines']), 'Kucingnya malah ikut duduk di kursi')
                widths = [box[2] - box[0] for box in result['text_bounds']]
                self.assertLess(max(widths) / min(widths), 1.3)
                left, top, right, bottom = result['backing_bounds']
                self.assertGreaterEqual(left, result['safe_inset'])
                self.assertLessEqual(right, width - result['safe_inset'])
                self.assertGreater(top, height * .1)
                self.assertLess(bottom, height * .45)
                with Image.open(self.output) as image:
                    alpha_bounds = image.getchannel('A').getbbox()
                    self.assertEqual(alpha_bounds, (left, top, right + 1, bottom + 1))

    def test_new_68_character_hook_does_not_use_three_lines(self):
        text = 'Gerakan kecil di ujung kain ini bikin lipatannya jadi terlihat rapi.'
        self.assertLessEqual(len(text), 68)
        result = self.overlay(text)
        self.assertLessEqual(result['line_count'], 2)
        self.assertGreaterEqual(result['font_size'], 22)
        self.assertFalse(result['legacy_fallback'])

    def test_short_phrase_can_remain_one_line(self):
        result = self.overlay('Kucing ikut duduk')
        self.assertEqual(result['lines'], ['Kucing ikut duduk'])
        self.assertEqual(result['font_size'], 30)

    def test_legacy_text_can_fall_back_to_three_lines_without_losing_words(self):
        text = 'Gerakan kecil di bagian ujung terlihat lebih jelas saat kameranya mendekat dan cahaya dari samping mengenai permukaannya.'
        result = self.overlay(text)
        self.assertEqual(result['line_count'], 3)
        self.assertTrue(result['legacy_fallback'])
        self.assertGreaterEqual(result['font_size'], 16)
        self.assertEqual(' '.join(result['lines']), text)
        result = self.overlay('ini ' * 39 + 'kini')
        self.assertEqual(len(' '.join(result['lines'])), 160)
        self.assertLessEqual(result['line_count'], 3)

    def test_oversized_tokens_are_held_instead_of_clipped_or_shrunk(self):
        for text in ['W' * 68, 'W' * 160]:
            with self.subTest(length=len(text)), self.assertRaises(Held) as error:
                self.overlay(text)
            self.assertEqual(error.exception.code, 'hook_too_wide')
            self.assertFalse(self.output.exists())

    def test_backing_is_compact_and_contrast_holds_over_white(self):
        result = self.overlay('Lihat bedanya sebelum lewat')
        boxes = result['text_bounds']
        left, top, right, bottom = result['backing_bounds']
        self.assertLessEqual(min(box[0] for box in boxes) - left, 10)
        self.assertLessEqual(bottom - max(box[3] for box in boxes), 7)
        with Image.open(self.output) as overlay:
            background = Image.new('RGBA', overlay.size, 'white')
            image = Image.alpha_composite(background, overlay)
            rgb = image.getpixel(((left + right) // 2, top + 1))[:3]
            values = [value / 255 for value in rgb]
            linear = [value / 12.92 if value <= .04045 else ((value + .055) / 1.055) ** 2.4 for value in values]
            luminance = sum(value * factor for value, factor in zip(linear, [.2126, .7152, .0722]))
            self.assertGreater(1.05 / (luminance + .05), 7)
            self.assertEqual(overlay.getpixel((0, 0))[3], 0)

    def test_empty_overlimit_and_tiny_video_are_rejected(self):
        for text in ['', ' \n ', 'x' * 161]:
            with self.subTest(text_length=len(text)), self.assertRaises(Held):
                self.overlay(text)
        with self.assertRaises(Held) as error:
            self.overlay('Hook singkat', 80, 60)
        self.assertEqual(error.exception.code, 'hook_dimensions')

    def test_whitespace_and_layout_are_deterministic(self):
        first = self.overlay('Lihat  bedanya\nsebelum lewat')
        image_bytes = self.output.read_bytes()
        second = self.overlay('Lihat bedanya sebelum lewat')
        self.assertEqual(first, second)
        self.assertEqual(image_bytes, self.output.read_bytes())
