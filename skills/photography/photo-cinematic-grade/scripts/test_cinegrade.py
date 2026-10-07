#!/usr/bin/env python3
"""Synthetic tests only. Temporary fixtures stay inside this skill directory."""
from __future__ import annotations

import copy
import hashlib
import io
import json
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import unittest
from unittest import mock
import zlib

from PIL import Image, ImageCms, PngImagePlugin

import cinegrade
import image_io

HERE = Path(__file__).resolve().parent


def png_chunks(blob):
    result = []
    offset = 8
    while offset < len(blob):
        length = int.from_bytes(blob[offset:offset + 4], 'big')
        result.append(blob[offset + 4:offset + 8])
        offset += length + 12
    return result


def add_chunk(blob, kind, data):
    chunk = struct.pack('>I', len(data)) + kind + data + struct.pack('>I', zlib.crc32(kind + data))
    return blob[:33] + chunk + blob[33:]


class Fixtures(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='.cinegrade-test-', dir=HERE)
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.image = Image.new('RGB', (3, 2))
        self.image.putdata([(0, 0, 0), (255, 255, 255), (255, 0, 0),
                            (0, 255, 0), (0, 0, 255), (127, 128, 129)])
        self.source = self.root / 'private-person-place.png'
        self.image.save(self.source)

    def rejection(self, path=None, **kwargs):
        with self.assertRaises(image_io.InputError):
            image_io.load_image(path or self.source, **kwargs)


class IOTests(Fixtures):
    def test_untagged_needs_explicit_assumption(self):
        self.rejection()
        loaded = image_io.load_image(self.source, assume_srgb=True)
        self.assertEqual(loaded.image.tobytes(), self.image.tobytes())
        self.assertEqual(loaded.provenance['color_management']['action'], 'explicit_srgb_assumption')
        self.assertIn('untagged_source_assumed_srgb', loaded.provenance['warnings'])

    def test_real_srgb_icc_conversion(self):
        profile = ImageCms.ImageCmsProfile(ImageCms.createProfile('sRGB')).tobytes()
        self.image.save(self.source, icc_profile=profile)
        loaded = image_io.load_image(self.source)
        self.assertEqual(loaded.image.tobytes(), self.image.tobytes())
        self.assertEqual(loaded.provenance['color_management']['source_icc_sha256'], hashlib.sha256(profile).hexdigest())
        self.assertEqual(loaded.provenance['color_management']['action'], 'icc_to_srgb')

    def test_icc_is_transformed_not_just_relabelled(self):
        profile = ImageCms.ImageCmsProfile(ImageCms.createProfile('sRGB')).tobytes()
        self.image.save(self.source, icc_profile=profile)
        expected = Image.new('RGB', self.image.size, (12, 34, 56))
        with mock.patch.object(ImageCms, 'profileToProfile', return_value=expected) as convert:
            loaded = image_io.load_image(self.source, assume_srgb=True)
        self.assertEqual(loaded.image.tobytes(), expected.tobytes())
        self.assertEqual(convert.call_args.kwargs['renderingIntent'], ImageCms.Intent.RELATIVE_COLORIMETRIC)
        self.assertEqual(convert.call_args.kwargs['outputMode'], 'RGB')
        self.assertEqual(convert.call_args.kwargs['flags'], 0)

    def test_bad_icc_never_uses_assumption_fallback(self):
        self.image.save(self.source, icc_profile=b'private broken profile')
        self.rejection(assume_srgb=True)
        lab_profile = ImageCms.ImageCmsProfile(ImageCms.createProfile('LAB')).tobytes()
        self.image.save(self.source, icc_profile=lab_profile)
        self.rejection(assume_srgb=True)

    def test_corrupt_icc_container_never_becomes_untagged(self):
        original = self.source.read_bytes()
        for data in (b'profile\x00\x00invalid-zlib', b'profile\x00\x00' + zlib.compress(b''),
                     b'profile\x00\x01invalid-method'):
            with self.subTest(data=data):
                self.source.write_bytes(add_chunk(original, b'iCCP', data))
                self.rejection(assume_srgb=True)
        profile = ImageCms.ImageCmsProfile(ImageCms.createProfile('sRGB')).tobytes()
        data = b'sRGB\x00\x00' + zlib.compress(profile)
        self.source.write_bytes(add_chunk(add_chunk(original, b'iCCP', data), b'iCCP', data))
        self.rejection(assume_srgb=True)
        # JPEG APP2 claims two ICC chunks, but only one is present.
        self.image.save(self.source, format='JPEG')
        original = self.source.read_bytes()
        data = b'ICC_PROFILE\x00\x01\x02incomplete-private-profile'
        self.source.write_bytes(original[:2] + b'\xff\xe2' + struct.pack('>H', len(data) + 2) + data + original[2:])
        self.rejection(assume_srgb=True)

    def test_all_eight_exif_orientations(self):
        # Manually enumerated pixel positions for the 3x2 source, not ImageOps.
        expected = {
            1: [0, 1, 2, 3, 4, 5], 2: [2, 1, 0, 5, 4, 3],
            3: [5, 4, 3, 2, 1, 0], 4: [3, 4, 5, 0, 1, 2],
            5: [0, 3, 1, 4, 2, 5], 6: [3, 0, 4, 1, 5, 2],
            7: [5, 2, 4, 1, 3, 0], 8: [2, 5, 1, 4, 0, 3],
        }
        pixels = list(self.image.getdata())
        for orientation, positions in expected.items():
            with self.subTest(orientation=orientation):
                exif = Image.Exif()
                exif[274] = orientation
                self.image.save(self.source, exif=exif)
                loaded = image_io.load_image(self.source, assume_srgb=True)
                self.assertEqual(list(loaded.image.getdata()), [pixels[i] for i in positions])
                self.assertEqual(loaded.image.size, (2, 3) if orientation >= 5 else (3, 2))
                self.assertEqual(loaded.image.info, {})

    def test_invalid_orientation_rejected(self):
        exif = Image.Exif()
        exif[274] = 9
        self.image.save(self.source, exif=exif)
        self.rejection(assume_srgb=True)

    def test_private_metadata_not_in_output_or_sidecar(self):
        exif = Image.Exif()
        exif[271] = 'PRIVATE_CAMERA_OWNER'
        exif[272] = 'PRIVATE_MODEL'
        exif[306] = '2026:01:02 03:04:05'
        exif[315] = 'PRIVATE_PERSON'
        exif[34853] = {1: 'N', 2: (31.0, 13.0, 0.0), 3: 'E', 4: (121.0, 28.0, 0.0)}
        exif[34665] = {33434: 0.01, 33437: 2.8, 34855: 400, 37386: 50.0,
                       36867: '2026:01:02 03:04:05', 42033: 'PRIVATE_SERIAL'}
        info = PngImagePlugin.PngInfo()
        info.add_text('Comment', 'PRIVATE_LOCATION')
        info.add_itxt('XML:com.adobe.xmp', 'PRIVATE_XMP')
        self.image.save(self.source, exif=exif, pnginfo=info)
        output = self.root / 'out'
        report = cinegrade.render(self.source, output, assume_srgb=True)
        receipt = (output / 'report.json').read_text()
        for forbidden in ('PRIVATE_', str(self.root), self.source.name, '2026:01:02', 'GPS', '121.'):
            self.assertNotIn(forbidden, receipt)
        safe = report['input']['technical_exif']
        self.assertEqual(safe, {'exposure_seconds': 0.01, 'f_number': 2.8, 'iso': 400.0, 'focal_length_mm': 50.0})
        encoded = (output / 'render.png').read_bytes()
        self.assertLessEqual(set(png_chunks(encoded)), {b'IHDR', b'iCCP', b'IDAT', b'IEND'})
        self.assertIn(b'iCCP', png_chunks(encoded))
        with Image.open(io.BytesIO(encoded)) as exported:
            self.assertFalse(exported.getexif())
            self.assertEqual(set(exported.info), {'icc_profile'})
            profile = ImageCms.ImageCmsProfile(io.BytesIO(exported.info['icc_profile']))
            self.assertIn('sRGB', ImageCms.getProfileDescription(profile))

    def test_technical_allowlist_rejects_text_nan_and_negative(self):
        exif = {33434: 'PRIVATE_VALUE', 33437: float('nan'), 34855: -1, 37386: True}
        self.assertEqual(image_io.technical_exif(exif), ({}, []))

    def test_unsupported_modes_and_transparency(self):
        for mode, fmt in [('RGBA', 'PNG'), ('LA', 'PNG'), ('P', 'PNG'), ('I;16', 'PNG'), ('CMYK', 'JPEG')]:
            with self.subTest(mode=mode):
                Image.new(mode, (3, 2)).save(self.source, format=fmt)
                self.rejection(assume_srgb=True)
        self.image.save(self.source, transparency=(0, 0, 0))
        self.rejection(assume_srgb=True)

    def test_grayscale_and_jpeg_are_explicitly_supported(self):
        for mode, fmt in [('L', 'PNG'), ('RGB', 'JPEG'), ('L', 'JPEG')]:
            with self.subTest(mode=mode, fmt=fmt):
                self.image.convert(mode).save(self.source, format=fmt)
                loaded = image_io.load_image(self.source, assume_srgb=True)
                self.assertEqual(loaded.image.mode, 'RGB')
                self.assertEqual(loaded.image.size, (3, 2))

    def test_animation_rejected(self):
        self.image.save(self.source, save_all=True, append_images=[Image.new('RGB', (3, 2), 'white')], duration=100, loop=0)
        self.rejection(assume_srgb=True)

    def test_gamma_and_chromaticity_not_silently_overridden(self):
        original = self.source.read_bytes()
        self.source.write_bytes(add_chunk(original, b'gAMA', struct.pack('>I', 100000)))
        self.rejection(assume_srgb=True)
        self.source.write_bytes(add_chunk(original, b'cHRM', struct.pack('>8I', *([30000] * 8))))
        self.rejection(assume_srgb=True)

    def test_hdr_chunks_rejected_even_when_pillow_ignores_them(self):
        original = self.source.read_bytes()
        for kind in (b'cICP', b'mDCv', b'cLLi'):
            with self.subTest(kind=kind):
                self.source.write_bytes(add_chunk(original, kind, b'\x09\x10\x00\x01'))
                self.rejection(assume_srgb=True)

    def test_corruption_and_size_guards(self):
        with mock.patch.object(image_io, 'MAX_SOURCE_BYTES', 1):
            self.rejection(assume_srgb=True)
        with mock.patch.object(image_io, 'MAX_PIXELS', 1):
            self.rejection(assume_srgb=True)
        self.source.write_bytes(self.source.read_bytes()[:-6])
        self.rejection(assume_srgb=True)
        self.source.write_bytes(b'not an image')
        self.rejection(assume_srgb=True)

    def test_symlink_and_nonregular_source_rejected(self):
        alias = self.root / 'alias.png'
        alias.symlink_to(self.source)
        self.rejection(alias, assume_srgb=True)
        self.rejection(self.root, assume_srgb=True)

    def test_new_directory_atomic_reservation_and_partial_retention(self):
        target = self.root / 'partial'
        # Simulate a disk failure only after the directory was reserved.
        with mock.patch.object(Path, 'open', side_effect=OSError('disk full')):
            with self.assertRaises(image_io.InputError):
                image_io.write_new_run(target, b'png', b'json')
        self.assertTrue(target.is_dir())
        with self.assertRaises(image_io.InputError):
            image_io.write_new_run(target, b'png', b'json')


class GradeTests(Fixtures):
    def setUp(self):
        super().setUp()
        self.looks = cinegrade.load_looks()

    def test_identity_neutral_and_strength_zero(self):
        ramp = Image.frombytes('RGB', (256, 1), bytes(v for x in range(256) for v in (x, 255 - x, x // 2)))
        for strength in (0, 1, 60, 100):
            graded, count = cinegrade.grade_pixels(ramp, self.looks['neutral'], strength)
            self.assertEqual(graded.tobytes(), ramp.tobytes())
            self.assertEqual(count, 0)
        for recipe in self.looks.values():
            graded, count = cinegrade.grade_pixels(ramp, recipe, 0)
            self.assertEqual(graded.tobytes(), ramp.tobytes())
            self.assertEqual(count, 0)

    def test_hand_computed_luma_curve_and_negative_rounding(self):
        recipe = copy.deepcopy(self.looks['neutral'])
        recipe['saturation_percent'] = 0
        graded, count = cinegrade.grade_pixels(self.image, recipe, 100)
        self.assertEqual(list(graded.getdata()), [(0, 0, 0), (255, 255, 255), (54, 54, 54),
                                                (182, 182, 182), (19, 19, 19), (128, 128, 128)])
        self.assertEqual(count, 0)
        curve = cinegrade.curve_table([[0, 8], [32, 24], [255, 247]])
        self.assertEqual([curve[x] for x in (0, 1, 16, 32, 128, 255)], [8, 9, 16, 24, 120, 247])
        self.assertEqual(cinegrade.round_div(-1, 2), 0)
        self.assertEqual(cinegrade.round_div(-3, 2), -1)

    def test_hand_computed_warm_muted_black_white_and_midgray(self):
        image = Image.new('RGB', (3, 1))
        image.putdata([(0, 0, 0), (255, 255, 255), (128, 128, 128)])
        graded, count = cinegrade.grade_pixels(image, self.looks['warm-muted'], 100)
        self.assertEqual(list(graded.getdata()), [(8, 9, 12), (253, 249, 245), (132, 130, 129)])
        self.assertEqual(count, 0)
        partial, _ = cinegrade.grade_pixels(image, self.looks['warm-muted'], 50)
        self.assertEqual(list(partial.getdata()), [(4, 5, 6), (254, 252, 250), (130, 129, 129)])

    def test_repeatability_and_source_pixels_unchanged(self):
        before = self.image.tobytes()
        for recipe in self.looks.values():
            a, n = cinegrade.grade_pixels(self.image, recipe, 60)
            b, m = cinegrade.grade_pixels(self.image, recipe, 60)
            self.assertEqual(a.tobytes(), b.tobytes())
            self.assertEqual(n, m)
        self.assertEqual(self.image.tobytes(), before)

    def test_endpoint_counts_and_preclamp_warning(self):
        qa = cinegrade.endpoint_qa(self.image)
        self.assertEqual(qa['pixel_count'], 6)
        self.assertEqual(qa['channel_endpoints'], {c: {'at_0': 3, 'at_255': 2} for c in 'rgb'})
        recipe = copy.deepcopy(self.looks['neutral'])
        recipe['shadow_rgb'] = [-16] * 3
        recipe['highlight_rgb'] = [16] * 3
        graded, count = cinegrade.grade_pixels(self.image, recipe, 100)
        self.assertEqual(count, 15)
        self.assertEqual(graded.tobytes()[:6], b'\x00\x00\x00\xff\xff\xff')

    def test_invalid_strength_and_mode(self):
        for value in (-1, 101, 1.5, float('nan'), True):
            with self.subTest(value=value), self.assertRaises(image_io.InputError):
                cinegrade.grade_pixels(self.image, self.looks['neutral'], value)
        with self.assertRaises(image_io.InputError):
            cinegrade.grade_pixels(self.image.convert('RGBA'), self.looks['neutral'], 50)

    def test_recipe_validation(self):
        path = self.root / 'looks.json'
        valid = {'schema_version': 1, 'looks': {'test': copy.deepcopy(self.looks['neutral'])}}
        for key, value in [('curve', [[0, 1], [0, 255]]), ('curve', [[0, 20], [255, 10]]),
                           ('curve', [[1, 0], [255, 255]]), ('curve', [[0, False], [255, 255]]),
                           ('shadow_rgb', [0, 0, 17]), ('highlight_rgb', [0, 0]),
                           ('saturation_percent', 121), ('label', ''), ('unknown', 1)]:
            data = copy.deepcopy(valid)
            data['looks']['test'][key] = value
            path.write_text(json.dumps(data))
            with self.subTest(key=key, value=value), self.assertRaises(image_io.InputError):
                cinegrade.load_looks(path)
        path.write_text('{invalid json')
        with self.assertRaises(image_io.InputError):
            cinegrade.load_looks(path)

    def test_complete_render_receipt_hashes_and_original_preservation(self):
        before = self.source.read_bytes()
        report = cinegrade.render(self.source, self.root / 'run1', assume_srgb=True)
        again = cinegrade.render(self.source, self.root / 'run2', assume_srgb=True)
        self.assertEqual(before, self.source.read_bytes())
        self.assertEqual(report['input']['source_sha256'], hashlib.sha256(before).hexdigest())
        self.assertEqual(report['output']['pixel_sha256'], again['output']['pixel_sha256'])
        output = self.root / 'run1'
        self.assertEqual(set(p.name for p in output.iterdir()), {'report.json', 'render.png'})
        self.assertEqual(json.loads((output / 'report.json').read_text()), report)
        self.assertEqual(report['output']['png_sha256'], hashlib.sha256((output / 'render.png').read_bytes()).hexdigest())
        with Image.open(output / 'render.png') as exported:
            self.assertEqual(report['output']['pixel_sha256'], hashlib.sha256(exported.tobytes()).hexdigest())

    def test_no_overwrite_files_directories_and_aliases(self):
        original = self.source.read_bytes()
        existing = self.root / 'existing'
        existing.mkdir()
        (existing / 'keep.txt').write_text('keep')
        alias = self.root / 'alias'
        alias.symlink_to(existing, target_is_directory=True)
        dangling = self.root / 'dangling'
        dangling.symlink_to(self.root / 'missing')
        for target in (self.source, self.root, existing, alias, dangling):
            with self.subTest(target=target.name), self.assertRaises(image_io.InputError):
                cinegrade.render(self.source, target, assume_srgb=True)
        self.assertEqual(self.source.read_bytes(), original)
        self.assertEqual((existing / 'keep.txt').read_text(), 'keep')
        self.assertFalse((existing / 'render.png').exists())

    def test_preflight_failures_leave_no_output(self):
        target = self.root / 'absent'
        for kwargs in ({}, {'assume_srgb': True, 'look': 'unknown'}, {'assume_srgb': True, 'strength': 101}):
            with self.subTest(kwargs=kwargs), self.assertRaises(image_io.InputError):
                cinegrade.render(self.source, target, **kwargs)
            self.assertFalse(target.exists())

    def test_cli_help_looks_and_error_contract(self):
        for args, expected in [(['--help'], 0), (['looks'], 0), (['compare'], 2),
                               (['render', str(self.source), '--output', str(self.root / 'out')], 2),
                               (['render', str(self.source), '--output', str(self.root / 'out'), '--strength', 'nan'], 2)]:
            proc = subprocess.run([sys.executable, '-B', str(HERE / 'cinegrade.py'), *args],
                                  capture_output=True, text=True, timeout=20)
            self.assertEqual(proc.returncode, expected, proc.stderr)
            self.assertNotIn('Traceback', proc.stderr)
            if args[0] == 'render' and '--strength' not in args:
                self.assertNotIn(self.source.name, proc.stderr)
        proc = subprocess.run([sys.executable, '-B', str(HERE / 'cinegrade.py'), 'render', str(self.source),
                               '--output', str(self.root / 'cli'), '--assume-srgb', '--look', 'neutral'],
                              capture_output=True, text=True, timeout=20)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(json.loads(proc.stdout)['status'], 'complete')
        self.assertNotIn(str(self.root), proc.stdout)


def run_tests(group='all'):
    suite = unittest.TestSuite()
    for cls in ([IOTests] if group == 'io' else [GradeTests] if group == 'grade' else [IOTests, GradeTests]):
        suite.addTests(unittest.defaultTestLoader.loadTestsFromTestCase(cls))
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    return 0 if result.wasSuccessful() else 1


if __name__ == '__main__':
    raise SystemExit(run_tests())
