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


class CandidateTests(Fixtures):
    def test_preview_integer_dimensions_no_upscale_and_minimum_one(self):
        cases = [((7, 5), 4, (4, 3)), ((5, 7), 4, (3, 4)),
                 ((4, 3), 2, (2, 2)), ((3, 4), 2, (2, 2)),
                 ((100, 1), 2, (2, 1)), ((1, 100), 2, (1, 2)),
                 ((3, 2), 3, (3, 2)), ((3, 2), 1024, (3, 2)),
                 ((3, 2), 1, (1, 1)), ((2049, 1), 2048, (2048, 1))]
        for size, cap, expected in cases:
            with self.subTest(size=size, cap=cap):
                image = Image.new('RGB', size, (17, 83, 201))
                before = image.tobytes()
                preview, record = cinegrade.candidate_preview(image, cap)
                self.assertEqual(preview.size, expected)
                self.assertEqual(preview.tobytes(), bytes((17, 83, 201)) * (expected[0] * expected[1]))
                self.assertEqual(image.tobytes(), before)
                self.assertEqual(record['resampling'], 'pillow-lanczos' if max(size) > cap else 'none')
                self.assertFalse(record['upscaled'])
                self.assertEqual(record['dimensions'], list(expected))
        with self.assertRaises(image_io.InputError):
            cinegrade.candidate_preview(self.image.convert('RGBA'), 1)

    def test_fixed_order_defaults_receipt_and_original_preservation(self):
        before = self.source.read_bytes()
        output = self.root / 'candidates'
        report = cinegrade.candidates(self.source, output, assume_srgb=True)
        self.assertEqual(self.source.read_bytes(), before)
        self.assertEqual(report['input']['source_sha256'], hashlib.sha256(before).hexdigest())
        self.assertEqual(report['skill_version'], '0.4.0')
        self.assertEqual(report['command'], 'candidates')
        self.assertEqual(report['selection'], {'automatic_selection': False, 'selected_look': None})
        self.assertEqual(report['preview']['max_edge'], 1024)
        expected_names = ['01-neutral.png', '02-warm-muted.png', '03-cool-muted.png']
        self.assertEqual([r['output']['file'] for r in report['candidates']], expected_names)
        self.assertEqual([r['grade']['look'] for r in report['candidates']], ['neutral', 'warm-muted', 'cool-muted'])
        self.assertEqual([r['grade']['strength_percent'] for r in report['candidates']], [0, 60, 60])
        self.assertEqual({p.name for p in output.iterdir()}, set(expected_names) | {'report.json'})
        self.assertEqual(json.loads((output / 'report.json').read_text()), report)
        for item in report['candidates']:
            blob = (output / item['output']['file']).read_bytes()
            self.assertEqual(item['output']['png_sha256'], hashlib.sha256(blob).hexdigest())
            with Image.open(io.BytesIO(blob)) as image:
                self.assertEqual(item['output']['pixel_sha256'], hashlib.sha256(image.tobytes()).hexdigest())
                self.assertEqual(image.size, (3, 2))
                self.assertEqual(image.mode, 'RGB')
                if item['grade']['look'] == 'neutral':
                    self.assertEqual(image.tobytes(), self.image.tobytes())

    def test_one_snapshot_one_icc_transform_before_resize(self):
        exif = Image.Exif()
        exif[274] = 6
        profile = ImageCms.ImageCmsProfile(ImageCms.createProfile('sRGB')).tobytes()
        self.image.save(self.source, exif=exif, icc_profile=profile)
        normalized = Image.new('RGB', (2, 3), (10, 30, 90))
        with mock.patch.object(image_io, '_read_source', wraps=image_io._read_source) as read, \
             mock.patch.object(ImageCms, 'profileToProfile', return_value=normalized) as convert, \
             mock.patch.object(cinegrade, 'candidate_preview', wraps=cinegrade.candidate_preview) as resize:
            report = cinegrade.candidates(self.source, self.root / 'out', max_edge=2)
        self.assertEqual(read.call_count, 1)
        self.assertEqual(convert.call_count, 1)
        self.assertEqual(convert.call_args.args[0].size, (2, 3))
        self.assertEqual(resize.call_count, 1)
        self.assertEqual(resize.call_args.args[0].tobytes(), normalized.tobytes())
        self.assertEqual(report['input']['orientation_applied'], 6)
        self.assertEqual(report['input']['oriented_dimensions'], [2, 3])
        self.assertEqual(report['preview']['dimensions'], [1, 2])
        self.assertEqual(report['preview']['processing_order'], ['exif_orientation', 'normalize_srgb', 'resize', 'grade'])
        with Image.open(self.root / 'out' / '01-neutral.png') as neutral:
            self.assertEqual(neutral.tobytes(), bytes((10, 30, 90)) * 2)

    def test_real_tagged_oriented_source_and_neutral_positions(self):
        exif = Image.Exif()
        exif[274] = 6
        profile = ImageCms.ImageCmsProfile(ImageCms.createProfile('sRGB')).tobytes()
        self.image.save(self.source, exif=exif, icc_profile=profile)
        report = cinegrade.candidates(self.source, self.root / 'out')
        with Image.open(self.root / 'out' / '01-neutral.png') as neutral:
            pixels = list(self.image.getdata())
            self.assertEqual(list(neutral.getdata()), [pixels[i] for i in [3, 0, 4, 1, 5, 2]])
            self.assertEqual(neutral.size, (2, 3))
        self.assertEqual(report['input']['color_management']['action'], 'icc_to_srgb')

    def test_lanczos_resize_precedes_grading_and_matches_render_of_preview(self):
        preview = self.image.resize((2, 1), Image.Resampling.LANCZOS, reducing_gap=None)
        preview_path = self.root / 'preview.png'
        preview_path.write_bytes(image_io.encode_png(preview))
        output = self.root / 'out'
        report = cinegrade.candidates(self.source, output, max_edge=2, strength=75, assume_srgb=True)
        self.assertEqual(report['qa']['scope'], 'resized_preview_only')
        self.assertEqual(report['qa']['before']['pixel_count'], 2)
        self.assertEqual(report['preview']['resampling'], 'pillow-lanczos')
        self.assertIsNone(report['preview']['reducing_gap'])
        for item in report['candidates']:
            name = item['grade']['look']
            amount = 0 if name == 'neutral' else 75
            rendered = cinegrade.render(preview_path, self.root / ('render-' + name), look=name, strength=amount)
            self.assertEqual(item['output']['pixel_sha256'], rendered['output']['pixel_sha256'])
            self.assertEqual(item['qa']['after'], rendered['qa']['after'])
            self.assertEqual(item['qa']['channel_sample_count'], 6)
        # This nonlinear fixture detects accidentally swapping resize and grade.
        full = cinegrade.render(self.source, self.root / 'full', strength=75, assume_srgb=True)
        with Image.open(self.root / 'full' / 'render.png') as image:
            wrong_order = image.resize((2, 1), Image.Resampling.LANCZOS).tobytes()
        warm_hash = report['candidates'][1]['output']['pixel_sha256']
        self.assertNotEqual(warm_hash, hashlib.sha256(wrong_order).hexdigest())
        self.assertEqual(full['output']['dimensions'], [3, 2])

    def test_hand_computed_candidates_and_full_strength_qa(self):
        Image.new('RGB', (1, 1), (128, 128, 128)).save(self.source)
        report = cinegrade.candidates(self.source, self.root / 'out', strength=50, assume_srgb=True)
        # Warm full-strength midgray is (132,130,129); 50% integer blend -> (130,129,129).
        with Image.open(self.root / 'out' / '02-warm-muted.png') as warm:
            self.assertEqual(warm.getpixel((0, 0)), (130, 129, 129))
        self.assertEqual(report['candidates'][0]['qa']['full_strength_pre_clamp_channel_samples'], 0)
        looks = cinegrade.load_looks()
        looks['warm-muted'] = copy.deepcopy(looks['neutral'])
        looks['warm-muted']['shadow_rgb'] = [-16] * 3
        looks['warm-muted']['highlight_rgb'] = [16] * 3
        self.image.save(self.source)
        with mock.patch.object(cinegrade, 'load_looks', return_value=looks):
            report = cinegrade.candidates(self.source, self.root / 'excursions', strength=1, assume_srgb=True)
        warm = report['candidates'][1]
        self.assertEqual(warm['qa']['full_strength_pre_clamp_channel_samples'], 15)
        self.assertEqual(warm['qa']['warnings'], ['grade_out_of_range_before_clamp'])
        self.assertEqual(warm['qa']['channel_sample_count'], 18)

    def test_repeatability_and_zero_strength_share_baseline(self):
        first = cinegrade.candidates(self.source, self.root / 'one', max_edge=2, assume_srgb=True)
        second = cinegrade.candidates(self.source, self.root / 'two', max_edge=2, assume_srgb=True)
        self.assertEqual([i['output']['pixel_sha256'] for i in first['candidates']],
                         [i['output']['pixel_sha256'] for i in second['candidates']])
        zero = cinegrade.candidates(self.source, self.root / 'zero', strength=0, max_edge=2, assume_srgb=True)
        self.assertEqual(len({i['output']['pixel_sha256'] for i in zero['candidates']}), 1)
        for item in zero['candidates']:
            self.assertEqual(item['qa']['full_strength_pre_clamp_channel_samples'], 0)
            self.assertEqual(item['qa']['warnings'], [])
        # The style-strength maximum is valid; neutral must still remain at zero.
        full = cinegrade.candidates(self.source, self.root / 'hundred', strength=100, assume_srgb=True)
        self.assertEqual([i['grade']['strength_percent'] for i in full['candidates']], [0, 100, 100])

    def test_private_metadata_absent_from_all_previews_and_receipt(self):
        exif = Image.Exif()
        exif[271] = 'PRIVATE_CAMERA'
        exif[315] = 'PRIVATE_OWNER'
        exif[306] = '2026:01:02 03:04:05'
        exif[34853] = {1: 'N', 2: (31.0, 13.0, 0.0)}
        exif[34665] = {33434: 0.01, 33437: 2.8, 34855: 400, 37386: 50.0, 42033: 'PRIVATE_SERIAL'}
        info = PngImagePlugin.PngInfo()
        info.add_text('Comment', 'PRIVATE_LOCATION')
        info.add_itxt('XML:com.adobe.xmp', 'PRIVATE_XMP')
        self.image.save(self.source, exif=exif, pnginfo=info)
        output = self.root / 'out'
        report = cinegrade.candidates(self.source, output, max_edge=2, assume_srgb=True)
        receipt = (output / 'report.json').read_text()
        for value in ('PRIVATE_', self.source.name, str(self.root), '2026:01:02', 'GPS'):
            self.assertNotIn(value, receipt)
        self.assertEqual(report['input']['technical_exif'],
                         {'exposure_seconds': 0.01, 'f_number': 2.8, 'iso': 400.0, 'focal_length_mm': 50.0})
        for item in report['candidates']:
            blob = (output / item['output']['file']).read_bytes()
            self.assertLessEqual(set(png_chunks(blob)), {b'IHDR', b'iCCP', b'IDAT', b'IEND'})
            self.assertIn(b'iCCP', png_chunks(blob))
            with Image.open(io.BytesIO(blob)) as image:
                self.assertFalse(image.getexif())
                self.assertEqual(set(image.info), {'icc_profile'})
                profile = ImageCms.ImageCmsProfile(io.BytesIO(image.info['icc_profile']))
                self.assertIn('sRGB', ImageCms.getProfileDescription(profile))

    def test_parameters_and_missing_recipes_rejected_before_source_read(self):
        target = self.root / 'absent'
        invalid = [{'strength': v} for v in (-1, 101, True, 1.5, '60', float('nan'))]
        invalid += [{'max_edge': v} for v in (0, -1, 2049, True, 2.5, '1024', float('inf'))]
        with mock.patch.object(cinegrade, 'load_image') as load:
            for kwargs in invalid:
                with self.subTest(kwargs=kwargs), self.assertRaises(image_io.InputError):
                    cinegrade.candidates(self.source, target, assume_srgb=True, **kwargs)
                self.assertFalse(target.exists())
            looks = cinegrade.load_looks()
            del looks['cool-muted']
            with mock.patch.object(cinegrade, 'load_looks', return_value=looks), self.assertRaises(image_io.InputError):
                cinegrade.candidates(self.source, target, assume_srgb=True)
            load.assert_not_called()

    def test_input_color_and_format_rejections_create_no_output(self):
        target = self.root / 'absent'
        with self.assertRaises(image_io.InputError):
            cinegrade.candidates(self.source, target)
        self.assertFalse(target.exists())
        for kwargs in ({'icc_profile': b'PRIVATE_BROKEN_PROFILE'}, {'transparency': (0, 0, 0)}):
            self.image.save(self.source, **kwargs)
            with self.subTest(kwargs=kwargs), self.assertRaises(image_io.InputError):
                cinegrade.candidates(self.source, target, assume_srgb=True)
            self.assertFalse(target.exists())
        Image.new('I;16', (3, 2)).save(self.source)
        with self.assertRaises(image_io.InputError):
            cinegrade.candidates(self.source, target, assume_srgb=True)
        self.assertFalse(target.exists())

    def test_no_overwrite_files_empty_directories_and_links(self):
        before = self.source.read_bytes()
        existing = self.root / 'existing'
        existing.mkdir()
        alias = self.root / 'alias'
        alias.symlink_to(existing, target_is_directory=True)
        dangling = self.root / 'dangling'
        dangling.symlink_to(self.root / 'missing')
        targets = [self.source, existing, alias, dangling, self.root]
        for target in targets:
            with self.subTest(target=target.name), self.assertRaises(image_io.InputError):
                cinegrade.candidates(self.source, target, assume_srgb=True)
        self.assertEqual(self.source.read_bytes(), before)
        self.assertEqual(list(existing.iterdir()), [])
        self.assertTrue(dangling.is_symlink())
        with self.assertRaises(image_io.InputError):
            cinegrade.candidates(self.source, self.root / 'missing-parent' / 'out', assume_srgb=True)
        self.assertFalse((self.root / 'missing-parent').exists())

    def test_all_encodes_finish_before_directory_reservation(self):
        target = self.root / 'absent'
        before = self.source.read_bytes()
        calls = []
        real_encode = cinegrade.encode_png
        def encode(image):
            self.assertFalse(target.exists())
            calls.append(image.size)
            if len(calls) == 3:
                raise image_io.InputError('synthetic encode failure')
            return real_encode(image)
        with mock.patch.object(cinegrade, 'encode_png', side_effect=encode), self.assertRaises(image_io.InputError):
            cinegrade.candidates(self.source, target, assume_srgb=True)
        self.assertEqual(len(calls), 3)
        self.assertFalse(target.exists())
        self.assertEqual(self.source.read_bytes(), before)

    def test_bundle_writes_report_last_and_preserves_partial_on_failure(self):
        target = self.root / 'partial'
        events = []
        real_open = Path.open
        def fail_second(path, *args, **kwargs):
            if path.parent == target:
                events.append(path.name)
                if path.name == '02-warm-muted.png':
                    raise OSError('synthetic disk full')
            return real_open(path, *args, **kwargs)
        with mock.patch.object(Path, 'open', fail_second), self.assertRaises(image_io.InputError):
            cinegrade.candidates(self.source, target, assume_srgb=True)
        self.assertEqual(events, ['01-neutral.png', '02-warm-muted.png'])
        self.assertEqual({p.name for p in target.iterdir()}, {'01-neutral.png'})
        before = (target / '01-neutral.png').read_bytes()
        with self.assertRaises(image_io.InputError):
            cinegrade.candidates(self.source, target, assume_srgb=True)
        self.assertEqual((target / '01-neutral.png').read_bytes(), before)
        events.clear()
        target = self.root / 'complete'
        def record_open(path, *args, **kwargs):
            if path.parent == target:
                events.append(path.name)
            return real_open(path, *args, **kwargs)
        with mock.patch.object(Path, 'open', record_open):
            cinegrade.candidates(self.source, target, assume_srgb=True)
        self.assertEqual(events, ['01-neutral.png', '02-warm-muted.png', '03-cool-muted.png', '.report.pending'])

    def test_bundle_directory_race_keeps_existing_content(self):
        target = self.root / 'raced'
        real_write = cinegrade.write_new_bundle
        def reserve_first(output, images, receipt):
            target.mkdir()
            (target / 'keep.txt').write_text('keep')
            real_write(output, images, receipt)
        with mock.patch.object(cinegrade, 'write_new_bundle', side_effect=reserve_first), self.assertRaises(image_io.InputError):
            cinegrade.candidates(self.source, target, assume_srgb=True)
        self.assertEqual({p.name for p in target.iterdir()}, {'keep.txt'})
        self.assertEqual((target / 'keep.txt').read_text(), 'keep')

    def test_bundle_rejects_paths_and_bad_payloads_before_mkdir(self):
        target = self.root / 'absent'
        for name in ('../escape.png', '/escape.png', 'nested/escape.png', 'nested\\escape.png',
                     'report.json', '.hidden.png', 'BAD.png', ''):
            with self.subTest(name=name), self.assertRaises(image_io.InputError):
                image_io.write_new_bundle(target, {name: b'png'}, b'{}')
            self.assertFalse(target.exists())
        for images, report in [({}, b'{}'), ({'x.png': 'text'}, b'{}'), ({'x.png': b'png'}, '{}')]:
            with self.assertRaises(image_io.InputError):
                image_io.write_new_bundle(target, images, report)
            self.assertFalse(target.exists())

    def test_cli_candidates_success_defaults_and_errors(self):
        args = cinegrade.build_parser().parse_args(['candidates', 'source.png', '--output', 'run'])
        self.assertEqual((args.strength, args.max_edge), (60, 1024))
        base = [sys.executable, '-B', str(HERE / 'cinegrade.py'), 'candidates', str(self.source)]
        for options in ([], ['--assume-srgb', '--max-edge', '0'], ['--assume-srgb', '--strength', '101'],
                        ['--max-edge', 'nan'], ['--look', 'neutral']):
            proc = subprocess.run([*base, '--output', str(self.root / 'absent'), *options],
                                  capture_output=True, text=True, timeout=20)
            self.assertEqual(proc.returncode, 2, proc.stderr)
            self.assertNotIn('Traceback', proc.stderr)
            self.assertFalse((self.root / 'absent').exists())
        proc = subprocess.run([*base, '--output', str(self.root / 'cli'), '--assume-srgb', '--max-edge', '2'],
                              capture_output=True, text=True, timeout=20)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        result = json.loads(proc.stdout)
        self.assertEqual(result['status'], 'complete')
        self.assertEqual(result['dimensions'], [2, 1])
        self.assertEqual(result['outputs'], ['01-neutral.png', '02-warm-muted.png', '03-cool-muted.png'])
        self.assertFalse(result['automatic_selection'])
        self.assertIn('untagged_source_assumed_srgb', result['warnings'])
        self.assertNotIn(str(self.root), proc.stdout)
        self.assertNotIn(self.source.name, proc.stdout)


    def test_report_write_flush_close_failures_leave_no_final_receipt(self):
        real_open = Path.open
        for stage in ('write', 'flush', 'close'):
            target = self.root / ('report-fault-' + stage)
            class FaultyStream:
                def __init__(self, stream):
                    self.stream = stream
                def __enter__(self):
                    return self
                def __exit__(self, kind, value, traceback):
                    self.stream.close()
                    if stage == 'close' and kind is None:
                        raise OSError('synthetic receipt close failure')
                    return False
                def write(self, data):
                    if stage == 'write':
                        self.stream.write(data[:3])
                        raise OSError('synthetic receipt write failure')
                    return self.stream.write(data)
                def flush(self):
                    if stage == 'flush':
                        raise OSError('synthetic receipt flush failure')
                    return self.stream.flush()
                def fileno(self):
                    return self.stream.fileno()
            def opened(path, *args, **kwargs):
                stream = real_open(path, *args, **kwargs)
                return FaultyStream(stream) if path.name == '.report.pending' else stream
            with self.subTest(stage=stage), mock.patch.object(Path, 'open', opened):
                with self.assertRaises(image_io.InputError):
                    cinegrade.candidates(self.source, target, assume_srgb=True)
            self.assertFalse((target / 'report.json').exists())
            self.assertTrue((target / '.report.pending').exists())
            self.assertTrue((target / '03-cool-muted.png').exists())

    def test_report_fsync_failure_leaves_no_final_receipt(self):
        target = self.root / 'report-fsync-fault'
        real_fsync = image_io.os.fsync
        calls = []
        def sync(fd):
            calls.append(fd)
            if len(calls) == 4:
                raise OSError('synthetic receipt fsync failure')
            return real_fsync(fd)
        with mock.patch.object(image_io.os, 'fsync', side_effect=sync):
            with self.assertRaises(image_io.InputError):
                cinegrade.candidates(self.source, target, assume_srgb=True)
        self.assertEqual(len(calls), 4)
        self.assertFalse((target / 'report.json').exists())
        self.assertEqual(json.loads((target / '.report.pending').read_text())['status'], 'complete')

    def test_receipt_publication_collision_never_overwrites(self):
        target = self.root / 'report-collision'
        real_link = image_io.os.link
        def collision(source, dest):
            Path(dest).write_bytes(b'keep-existing-receipt')
            return real_link(source, dest)
        with mock.patch.object(image_io.os, 'link', side_effect=collision):
            with self.assertRaises(image_io.InputError):
                cinegrade.candidates(self.source, target, assume_srgb=True)
        self.assertEqual((target / 'report.json').read_bytes(), b'keep-existing-receipt')
        self.assertTrue((target / '.report.pending').exists())

    def test_receipt_publication_failure_preserves_pending(self):
        target = self.root / 'report-link-failure'
        with mock.patch.object(image_io.os, 'link', side_effect=OSError('hard links unavailable')):
            with self.assertRaises(image_io.InputError):
                cinegrade.candidates(self.source, target, assume_srgb=True)
        self.assertFalse((target / 'report.json').exists())
        self.assertTrue((target / '.report.pending').exists())

    def test_optional_pending_cleanup_failure_is_not_false_failure(self):
        target = self.root / 'report-cleanup-failure'
        real_unlink = Path.unlink
        def unlink(path, *args, **kwargs):
            if path.parent == target and path.name == '.report.pending':
                raise OSError('synthetic optional cleanup failure')
            return real_unlink(path, *args, **kwargs)
        with mock.patch.object(Path, 'unlink', unlink):
            report = cinegrade.candidates(self.source, target, assume_srgb=True)
        self.assertEqual(report['status'], 'complete')
        self.assertEqual((target / '.report.pending').read_bytes(), (target / 'report.json').read_bytes())
        for candidate in report['candidates']:
            self.assertEqual(hashlib.sha256((target / candidate['output']['file']).read_bytes()).hexdigest(),
                             candidate['output']['png_sha256'])



class CompareTests(Fixtures):
    # Synthetic pixels only. Values below are test inputs, not observed photos
    # or new grading recipes; no photographic-effect approval is implied.
    def compare(self, target="comparison", **kwargs):
        options = {"look": "warm-muted", "strength": 50, "assume_srgb": True}
        options.update(kwargs)
        return cinegrade.compare(self.source, self.root / target, **options)

    def test_full_resolution_pair_matches_original_and_render(self):
        before = self.source.read_bytes()
        expected = cinegrade.render(self.source, self.root / "rendered", look="warm-muted",
                                    strength=50, assume_srgb=True)
        report = self.compare()
        target = self.root / "comparison"
        self.assertEqual(set(p.name for p in target.iterdir()), {"compare.png", "report.json"})
        self.assertEqual(report["command"], "compare")
        self.assertEqual(report["output"]["dimensions"], [6, 2])
        self.assertEqual(report["panels"][0]["box_xywh"], [0, 0, 3, 2])
        self.assertEqual(report["panels"][1]["box_xywh"], [3, 0, 3, 2])
        self.assertEqual([p["role"] for p in report["panels"]], ["before", "after"])
        self.assertEqual(report["panels"][1]["pixel_sha256"], expected["output"]["pixel_sha256"])
        self.assertEqual(report["grade"], expected["grade"])
        self.assertEqual(report["qa"]["before"], expected["qa"]["before"])
        self.assertEqual(report["qa"]["after"], expected["qa"]["after"])
        self.assertEqual(report["qa"]["scope"], "full_resolution_panels")
        self.assertEqual(report["qa"]["channel_sample_count"], 18)
        blob = (target / "compare.png").read_bytes()
        self.assertEqual(report["output"]["png_sha256"], hashlib.sha256(blob).hexdigest())
        self.assertEqual(json.loads((target / "report.json").read_text()), report)
        with Image.open(io.BytesIO(blob)) as image:
            self.assertEqual(image.mode, "RGB")
            self.assertEqual(image.size, (6, 2))
            self.assertEqual(image.crop((0, 0, 3, 2)).tobytes(), self.image.tobytes())
            self.assertEqual(report["output"]["pixel_sha256"], hashlib.sha256(image.tobytes()).hexdigest())
            self.assertEqual(report["panels"][0]["pixel_sha256"], hashlib.sha256(self.image.tobytes()).hexdigest())
            with Image.open(self.root / "rendered/render.png") as rendered:
                self.assertEqual(image.crop((3, 0, 6, 2)).tobytes(), rendered.tobytes())
        self.assertEqual(self.source.read_bytes(), before)
        self.assertEqual(report["input"]["source_sha256"], hashlib.sha256(before).hexdigest())

    def test_hand_computed_pixels_and_no_preview_resize(self):
        image = Image.new("RGB", (3, 1))
        image.putdata([(0, 0, 0), (255, 255, 255), (128, 128, 128)])
        image.save(self.source)
        with mock.patch.object(cinegrade, "candidate_preview", side_effect=AssertionError("must not resize")):
            self.compare()
        with Image.open(self.root / "comparison/compare.png") as result:
            self.assertEqual(list(result.getdata()), [(0, 0, 0), (255, 255, 255), (128, 128, 128),
                                                      (4, 5, 6), (254, 252, 250), (130, 129, 129)])

    def test_all_exif_orientations_use_same_normalized_baseline(self):
        positions = {1: [0, 1, 2, 3, 4, 5], 2: [2, 1, 0, 5, 4, 3],
                     3: [5, 4, 3, 2, 1, 0], 4: [3, 4, 5, 0, 1, 2],
                     5: [0, 3, 1, 4, 2, 5], 6: [3, 0, 4, 1, 5, 2],
                     7: [5, 2, 4, 1, 3, 0], 8: [2, 5, 1, 4, 0, 3]}
        pixels = list(self.image.getdata())
        profile = ImageCms.ImageCmsProfile(ImageCms.createProfile("sRGB")).tobytes()
        for orientation, order in positions.items():
            exif = Image.Exif()
            exif[274] = orientation
            self.image.save(self.source, icc_profile=profile, exif=exif)
            report = self.compare(str(orientation), look="neutral", strength=100, assume_srgb=False)
            width, height = (2, 3) if orientation >= 5 else (3, 2)
            with Image.open(self.root / str(orientation) / "compare.png") as result:
                self.assertEqual(result.size, (2 * width, height))
                self.assertEqual(list(result.crop((0, 0, width, height)).getdata()), [pixels[i] for i in order])
                self.assertEqual(result.crop((0, 0, width, height)).tobytes(),
                                 result.crop((width, 0, 2 * width, height)).tobytes())
            self.assertEqual(report["input"]["orientation_applied"], orientation)

    def test_one_snapshot_one_icc_transform_no_second_read(self):
        profile = ImageCms.ImageCmsProfile(ImageCms.createProfile("sRGB")).tobytes()
        self.image.save(self.source, icc_profile=profile)
        normalized = Image.new("RGB", (3, 2), (17, 83, 201))
        with mock.patch.object(image_io, "_read_source", wraps=image_io._read_source) as read, \
             mock.patch.object(ImageCms, "profileToProfile", return_value=normalized) as convert:
            report = self.compare(assume_srgb=False)
        self.assertEqual(read.call_count, 1)
        self.assertEqual(convert.call_count, 1)
        self.assertEqual(report["panels"][0]["pixel_sha256"], hashlib.sha256(normalized.tobytes()).hexdigest())
        self.assertEqual(report["input"]["color_management"]["action"], "icc_to_srgb")

    def test_zero_neutral_repeatability_and_single_pixel(self):
        for look in cinegrade.load_looks():
            for strength in ((0, 100) if look == "neutral" else (0,)):
                report = self.compare(look + str(strength), look=look, strength=strength)
                self.assertEqual(report["panels"][0]["pixel_sha256"], report["panels"][1]["pixel_sha256"])
        first = self.compare("first")
        second = self.compare("second")
        self.assertEqual(first["output"]["pixel_sha256"], second["output"]["pixel_sha256"])
        Image.new("RGB", (1, 1), (128, 128, 128)).save(self.source)
        report = self.compare("single")
        self.assertEqual(report["output"]["dimensions"], [2, 1])

    def test_qa_counts_one_panel_and_reports_excursions(self):
        looks = cinegrade.load_looks()
        looks["warm-muted"] = copy.deepcopy(looks["neutral"])
        looks["warm-muted"]["shadow_rgb"] = [-16] * 3
        looks["warm-muted"]["highlight_rgb"] = [16] * 3
        with mock.patch.object(cinegrade, "load_looks", return_value=looks):
            report = self.compare(strength=1)
        self.assertEqual(report["qa"]["channel_sample_count"], 18)
        self.assertEqual(report["qa"]["before"]["pixel_count"], 6)
        self.assertEqual(report["qa"]["after"]["pixel_count"], 6)
        self.assertEqual(report["qa"]["full_strength_pre_clamp_channel_samples"], 15)
        self.assertIn("grade_out_of_range_before_clamp", report["qa"]["warnings"])

    def test_privacy_profile_and_no_source_metadata(self):
        exif = Image.Exif()
        exif[315] = "PRIVATE_OWNER"
        exif[34853] = {1: "N", 2: (31.0, 13.0, 0.0)}
        exif[34665] = {33434: 0.01, 33437: 2.8, 34855: 400, 37386: 50.0, 42033: "PRIVATE_SERIAL"}
        info = PngImagePlugin.PngInfo()
        info.add_text("Comment", "PRIVATE_LOCATION")
        info.add_itxt("XML:com.adobe.xmp", "PRIVATE_XMP")
        self.image.save(self.source, exif=exif, pnginfo=info)
        report = self.compare()
        text = (self.root / "comparison/report.json").read_text()
        for secret in ("PRIVATE_", "GPS", self.source.name, str(self.root)):
            self.assertNotIn(secret, text)
        self.assertEqual(report["input"]["technical_exif"],
                         {"exposure_seconds": 0.01, "f_number": 2.8, "iso": 400.0, "focal_length_mm": 50.0})
        blob = (self.root / "comparison/compare.png").read_bytes()
        self.assertLessEqual(set(png_chunks(blob)), {b"IHDR", b"iCCP", b"IDAT", b"IEND"})
        with Image.open(io.BytesIO(blob)) as result:
            self.assertEqual(set(result.info), {"icc_profile"})
            profile = ImageCms.ImageCmsProfile(io.BytesIO(result.info["icc_profile"]))
            self.assertIn("sRGB", ImageCms.getProfileDescription(profile))
            self.assertFalse(result.getexif())

    def test_invalid_parameters_rejected_before_source_read(self):
        invalid = [{"strength": v} for v in (-1, 101, True, 1.5, float("nan"), "50")]
        invalid += [{"look": "unknown"}]
        with mock.patch.object(cinegrade, "load_image") as load:
            for options in invalid:
                with self.subTest(options=options), self.assertRaises(image_io.InputError):
                    self.compare(**options)
                self.assertFalse((self.root / "comparison").exists())
            load.assert_not_called()

    def test_input_rejections_leave_no_output(self):
        with self.assertRaises(image_io.InputError):
            self.compare(assume_srgb=False)
        for options in ({"icc_profile": b"PRIVATE_INVALID"}, {"transparency": (0, 0, 0)}):
            self.image.save(self.source, **options)
            with self.assertRaises(image_io.InputError):
                self.compare()
            self.assertFalse((self.root / "comparison").exists())
        Image.new("I;16", (3, 2)).save(self.source)
        with self.assertRaises(image_io.InputError):
            self.compare()
        self.assertFalse((self.root / "comparison").exists())

    def test_existing_outputs_and_links_preserved(self):
        before = self.source.read_bytes()
        existing = self.root / "existing"
        existing.mkdir()
        alias = self.root / "alias"
        alias.symlink_to(existing, target_is_directory=True)
        dangling = self.root / "dangling"
        dangling.symlink_to(self.root / "missing")
        for target in (self.source, self.root, existing, alias, dangling):
            with self.subTest(target=target), self.assertRaises(image_io.InputError):
                cinegrade.compare(self.source, target, look="neutral", strength=0, assume_srgb=True)
        self.assertEqual(self.source.read_bytes(), before)
        self.assertEqual(list(existing.iterdir()), [])
        self.assertTrue(dangling.is_symlink())
        with self.assertRaises(image_io.InputError):
            self.compare("missing-parent/out")
        self.assertFalse((self.root / "missing-parent").exists())

    def test_encode_failure_before_output_reservation(self):
        with mock.patch.object(cinegrade, "encode_png", side_effect=image_io.InputError("synthetic encoding failure")):
            with self.assertRaises(image_io.InputError):
                self.compare()
        self.assertFalse((self.root / "comparison").exists())

    def test_write_failure_preserves_partial_without_final_receipt(self):
        target = self.root / "comparison"
        real_open = Path.open
        def fail_receipt(path, *args, **kwargs):
            if path.parent == target and path.name == ".report.pending":
                raise OSError("synthetic disk full")
            return real_open(path, *args, **kwargs)
        with mock.patch.object(Path, "open", fail_receipt), self.assertRaises(image_io.InputError):
            self.compare()
        self.assertEqual(set(p.name for p in target.iterdir()), {"compare.png"})
        before = (target / "compare.png").read_bytes()
        with self.assertRaises(image_io.InputError):
            self.compare()
        self.assertEqual((target / "compare.png").read_bytes(), before)

    def test_cli_explicit_selection_and_error_contract(self):
        base = [sys.executable, "-B", str(HERE / "cinegrade.py"), "compare", str(self.source),
                "--output", str(self.root / "cli")]
        for options in ([], ["--look", "neutral"], ["--strength", "0"],
                        ["--look", "neutral", "--strength", "101", "--assume-srgb"],
                        ["--look", "neutral", "--strength", "0"]):
            proc = subprocess.run([*base, *options], capture_output=True, text=True, timeout=20)
            self.assertEqual(proc.returncode, 2, proc.stderr)
            self.assertNotIn("Traceback", proc.stderr)
            self.assertFalse((self.root / "cli").exists())
        proc = subprocess.run([*base, "--look", "warm-muted", "--strength", "50", "--assume-srgb"],
                              capture_output=True, text=True, timeout=20)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        result = json.loads(proc.stdout)
        self.assertEqual(result["status"], "complete")
        self.assertEqual(result["command"], "compare")
        self.assertEqual(result["output"], "compare.png")
        self.assertEqual(result["dimensions"], [6, 2])
        self.assertIn("untagged_source_assumed_srgb", result["warnings"])
        self.assertNotIn(str(self.root), proc.stdout)
        self.assertNotIn(self.source.name, proc.stdout)

def run_tests(group='all'):
    suite = unittest.TestSuite()
    for cls in ([IOTests] if group == 'io' else [GradeTests, CandidateTests, CompareTests] if group == 'grade' else [IOTests, GradeTests, CandidateTests, CompareTests]):
        suite.addTests(unittest.defaultTestLoader.loadTestsFromTestCase(cls))
    if group != "io":
        from test_color_core import ColorCoreTests, HighlightRolloffTests
        suite.addTests(unittest.defaultTestLoader.loadTestsFromTestCase(ColorCoreTests))
        suite.addTests(unittest.defaultTestLoader.loadTestsFromTestCase(HighlightRolloffTests))
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    return 0 if result.wasSuccessful() else 1


if __name__ == '__main__':
    raise SystemExit(run_tests())
