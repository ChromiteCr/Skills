# SYNTHETIC mathematical and CLI fixtures only. Constructed ramps, colors,
# metadata, faults and strengths test contracts; they are not photographs,
# observed scene measurements or user-confirmed creative settings.
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

import numpy as np
from PIL import Image, ImageCms, PngImagePlugin

import cinegrade
import color_core
import image_io
import srgb16

HERE = Path(__file__).resolve().parent


def decode_rgb16(blob):
    # Independent byte-level PNG readback. Pillow would silently expose RGB16
    # as RGB8, so it is deliberately NOT our sample-precision oracle.
    assert blob[:8] == b"\x89PNG\r\n\x1a\n"
    offset, chunks = 8, []
    while offset < len(blob):
        length, = struct.unpack_from(">I", blob, offset)
        kind = blob[offset + 4:offset + 8]
        payload = blob[offset + 8:offset + 8 + length]
        checksum, = struct.unpack_from(">I", blob, offset + 8 + length)
        assert checksum == zlib.crc32(kind + payload)
        assert len(payload) == length
        chunks.append((kind, payload))
        offset += length + 12
    assert offset == len(blob)
    assert chunks[0][0] == b"IHDR" and chunks[-1] == (b"IEND", b"")
    w, h, depth, kind, comp, filt, interlace = struct.unpack(">IIBBBBB", chunks[0][1])
    assert (depth, kind, comp, filt, interlace) == (16, 2, 0, 0, 0)
    raw = zlib.decompress(b"".join(p for k, p in chunks if k == b"IDAT"))
    stride = 6 * w + 1
    assert len(raw) == h * stride
    rows = []
    for y in range(h):
        assert raw[y * stride] == 0
        rows.append(struct.unpack(">" + str(3 * w) + "H", raw[y * stride + 1:(y + 1) * stride]))
    return np.array(rows, dtype=np.uint16).reshape(h, w, 3), chunks


class Png16Tests(unittest.TestCase):
    def setUp(self):
        local = HERE.parents[3] / ".git"
        self.temp = tempfile.TemporaryDirectory(prefix="synthetic-png16-", dir=local if local.is_dir() else HERE)
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root / "SYNTHETIC_PRIVATE_SOURCE.png"
        axis = np.arange(256, dtype=np.uint8)
        self.rgb = np.stack((axis, axis[::-1], np.roll(axis, 64)), axis=-1).reshape(2, 128, 3)
        self.image = Image.frombytes("RGB", (128, 2), self.rgb.tobytes())
        self.image.save(self.source)

    def render(self, name="out", **kwargs):
        return cinegrade.render(self.source, self.root / name, assume_srgb=True, bit_depth=16, **kwargs)

    def test_quantize_hand_values(self):
        values = [[0, 0.5, 1], [0.25, 0.75, 1 / 65535]]
        np.testing.assert_array_equal(srgb16.quantize_srgb16(values), [[0, 32768, 65535], [16384, 49151, 1]])

    def test_quantize_all_65536_sample_codes(self):
        axis = np.arange(65536, dtype=np.uint16)
        values = np.repeat((axis.astype(float) / 65535)[:, None], 3, axis=1)
        actual = srgb16.quantize_srgb16(values)
        np.testing.assert_array_equal(actual[:, 0], axis)
        self.assertEqual(len(np.unique(actual[:, 1])), 65536)

    def test_quantize_half_step_neighbors(self):
        values = [np.nextafter(0.5, 0), 0.5, np.nextafter(0.5, 1)]
        np.testing.assert_array_equal(srgb16.quantize_srgb16(values), [32767, 32768, 32768])

    def test_quantize_rejects_nonfinite_and_out_of_gamut(self):
        for value in (float("nan"), float("inf"), -float("inf"), np.nextafter(0., -1), np.nextafter(1., 2)):
            with self.subTest(value=value), self.assertRaises(image_io.InputError):
                srgb16.quantize_srgb16([value, 0, 1])

    def test_quantize_rejects_bad_shapes_and_types(self):
        for value in ([], 0.5, [0, 1], [True, False, True], ["0", "1", "0"], [1j, 0, 1], np.array([0, 0, 1], dtype=object)):
            with self.subTest(value=str(value)), self.assertRaises(image_io.InputError):
                srgb16.quantize_srgb16(value)

    def test_quantize_noncontiguous_readonly_and_independent(self):
        values = np.linspace(0, 1, 60).reshape(4, 5, 3).transpose(1, 0, 2)
        before = values.copy()
        values.setflags(write=False)
        actual = srgb16.quantize_srgb16(values)
        self.assertEqual(actual.dtype, np.uint16)
        np.testing.assert_array_equal(values, before)
        self.assertFalse(np.shares_memory(values, actual))
        actual[:] = 0
        np.testing.assert_array_equal(values, before)

    def test_png_big_endian_rgb_channels_and_rows(self):
        values = np.array([[[1, 256, 65535], [32768, 2, 3]], [[4, 5, 6], [65534, 513, 0]]], dtype=np.uint16)
        actual, _ = decode_rgb16(srgb16.encode_png16(values))
        np.testing.assert_array_equal(actual, values)

    def test_png_noncontiguous_and_explicit_endian_inputs(self):
        values = np.arange(60, dtype=np.uint16).reshape(4, 5, 3).transpose(1, 0, 2)
        for samples in (values, values.astype(">u2"), values.astype("<u2")):
            samples.setflags(write=False)
            actual, _ = decode_rgb16(srgb16.encode_png16(samples))
            np.testing.assert_array_equal(actual, values)

    def test_png_rejects_wrong_depth_shape_or_type(self):
        bad = (self.rgb, self.rgb.astype(float), self.rgb.astype(np.int16), np.zeros((2, 2), dtype=np.uint16),
               np.zeros((2, 2, 4), dtype=np.uint16), np.zeros((0, 2, 3), dtype=np.uint16))
        for value in bad:
            with self.subTest(shape=value.shape, dtype=value.dtype), self.assertRaises(image_io.InputError):
                srgb16.encode_png16(value)

    def test_png_pixel_limit(self):
        with mock.patch.object(srgb16, "MAX_PIXELS", 1), self.assertRaises(image_io.InputError):
            srgb16.encode_png16(self.rgb.astype(np.uint16))

    def test_png_icc_crc_and_metadata_allowlist(self):
        blob = srgb16.encode_png16(self.rgb.astype(np.uint16) * 257)
        _, chunks = decode_rgb16(blob)
        self.assertLessEqual({k for k, p in chunks}, {b"IHDR", b"iCCP", b"IDAT", b"IEND"})
        profiles = [p for k, p in chunks if k == b"iCCP"]
        self.assertEqual(len(profiles), 1)
        self.assertTrue(profiles[0].startswith(b"sRGB\x00\x00"))
        profile = zlib.decompress(profiles[0][6:])
        self.assertEqual(profile, srgb16.PROFILE.read_bytes())
        self.assertEqual(hashlib.sha256(profile).hexdigest(), srgb16.PROFILE_SHA256)
        parsed = ImageCms.ImageCmsProfile(io.BytesIO(profile))
        self.assertIn("sRGB", ImageCms.getProfileDescription(parsed))
        normalized = ImageCms.profileToProfile(self.image, parsed, ImageCms.createProfile("sRGB"), outputMode="RGB",
                                               renderingIntent=ImageCms.Intent.RELATIVE_COLORIMETRIC)
        self.assertEqual(normalized.tobytes(), self.image.tobytes())
        with Image.open(io.BytesIO(blob)) as opened:
            opened.load()
            self.assertEqual(opened.size, self.image.size)
            self.assertEqual(set(opened.info), {"icc_profile"})

    def test_encoder_does_not_create_time_dependent_icc(self):
        samples = self.rgb.astype(np.uint16) * 257
        with mock.patch.object(ImageCms, "createProfile", side_effect=AssertionError("no runtime profile stamping")):
            self.assertEqual(srgb16.encode_png16(samples), srgb16.encode_png16(samples))

    def test_missing_or_corrupt_fixed_profile_rejected(self):
        missing = self.root / "missing.icc"
        corrupt = self.root / "corrupt.icc"
        corrupt.write_bytes(b"SYNTHETIC corrupt profile")
        for path in (missing, corrupt):
            with mock.patch.object(srgb16, "PROFILE", path), self.assertRaises(image_io.InputError):
                srgb16.encode_png16(self.rgb.astype(np.uint16))

    def test_float_pipeline_preserves_more_than_8bit_precision(self):
        # SYNTHETIC linear-light ramp, not a measured photograph or look recipe.
        ramp = np.linspace(0, 1, 1024)
        linear = np.stack((ramp, ramp[::-1], ramp), axis=-1).reshape(4, 256, 3)
        mapped, qa = color_core.gamut_map_linear_srgb(linear)
        self.assertEqual(qa["pixels_mapped"], 0)
        encoded = color_core.linear_to_srgb(mapped)
        actual, _ = decode_rgb16(srgb16.encode_png16(srgb16.quantize_srgb16(encoded)))
        self.assertGreater(len(np.unique(actual[..., 0])), 256)
        self.assertTrue(np.any(actual % 257 != 0))
        self.assertLessEqual(np.max(np.abs(actual.astype(float) / 65535 - encoded)), 0.5 / 65535)

    def test_render_all_existing_looks_preserve_exact_rgb8_grade(self):
        loaded = image_io.load_image(self.source, assume_srgb=True)
        for name, recipe in cinegrade.load_looks().items():
            with self.subTest(look=name):
                expected, _ = cinegrade.grade_pixels(loaded.image, recipe, 60)
                report = self.render(name, look=name, strength=60)
                blob = (self.root / name / "render.png").read_bytes()
                actual, _ = decode_rgb16(blob)
                np.testing.assert_array_equal(actual, np.asarray(expected).astype(np.uint16) * 257)
                self.assertEqual(report["output"]["png_sha256"], hashlib.sha256(blob).hexdigest())
                raw = struct.pack(">" + str(actual.size) + "H", *actual.ravel())
                self.assertEqual(report["output"]["pixel_sha256"], hashlib.sha256(raw).hexdigest())

    def test_render_zero_strength_all_256_codes(self):
        self.render(strength=0)
        actual, _ = decode_rgb16((self.root / "out/render.png").read_bytes())
        np.testing.assert_array_equal(actual, self.rgb.astype(np.uint16) * 257)

    def test_render_precision_disclosure_and_published_report(self):
        report = self.render()
        self.assertEqual(report, json.loads((self.root / "out/report.json").read_text()))
        self.assertEqual(report["output"]["bit_depth"], 16)
        self.assertEqual(report["output"]["export_version"], "0.18.0")
        self.assertEqual(report["output"]["sample_encoding"], "RGB_uint16_big_endian_row_major")
        self.assertEqual(report["output"]["precision"], {"source_bits": 8, "grading_bits": 8,
                         "expansion": "uint8_times_257", "adds_detail": False})
        self.assertEqual(report["qa"]["reference_samples"], "legacy_RGB8_before_lossless_16bit_expansion")
        self.assertIn("16bit_container_from_8bit_grade_no_added_precision", report["qa"]["warnings"])

    def test_render_orientation_icc_and_private_metadata(self):
        exif = Image.Exif()
        exif[274] = 6
        exif[315] = "SYNTHETIC_PRIVATE_OWNER"
        info = PngImagePlugin.PngInfo()
        info.add_text("Comment", "SYNTHETIC_PRIVATE_LOCATION")
        self.image.save(self.source, exif=exif, pnginfo=info, icc_profile=srgb16.PROFILE.read_bytes())
        report = self.render(strength=0)
        blob = (self.root / "out/render.png").read_bytes()
        actual, chunks = decode_rgb16(blob)
        np.testing.assert_array_equal(actual, np.rot90(self.rgb, k=3).astype(np.uint16) * 257)
        self.assertEqual(report["input"]["orientation_applied"], 6)
        self.assertEqual(report["input"]["color_management"]["action"], "icc_to_srgb")
        self.assertNotIn("SYNTHETIC_PRIVATE", json.dumps(report))
        self.assertNotIn(str(self.root), json.dumps(report))
        self.assertFalse({b"eXIf", b"tEXt", b"iTXt", b"zTXt"} & {k for k, p in chunks})

    def test_render_preserves_source_and_occupied_outputs(self):
        before = self.source.read_bytes()
        existing = self.root / "existing"
        existing.mkdir()
        alias = self.root / "alias"
        alias.symlink_to(existing, target_is_directory=True)
        dangling = self.root / "dangling"
        dangling.symlink_to(self.root / "missing")
        for target in (self.source, self.root, existing, alias, dangling):
            with self.subTest(target=target.name), self.assertRaises(image_io.InputError):
                cinegrade.render(self.source, target, assume_srgb=True, bit_depth=16)
        self.assertEqual(self.source.read_bytes(), before)
        self.assertEqual(list(existing.iterdir()), [])
        self.assertTrue(dangling.is_symlink())

    def test_render_encoding_failure_writes_nothing(self):
        with mock.patch.object(srgb16, "encode_png16", side_effect=image_io.InputError("synthetic encoder fault")):
            with self.assertRaises(image_io.InputError):
                self.render()
        self.assertFalse((self.root / "out").exists())

    def test_render_partial_write_keeps_no_completion_receipt(self):
        target = self.root / "out"
        real_open = Path.open
        def fail_report(path, *args, **kwargs):
            if path.parent == target and path.name == ".report.pending":
                raise OSError("SYNTHETIC disk failure")
            return real_open(path, *args, **kwargs)
        with mock.patch.object(Path, "open", fail_report), self.assertRaises(image_io.InputError):
            self.render()
        self.assertEqual({p.name for p in target.iterdir()}, {"render.png"})
        decode_rgb16((target / "render.png").read_bytes())
        with self.assertRaises(image_io.InputError):
            self.render()

    def test_render_rejects_invalid_bit_depth_without_writes(self):
        for value in (True, 0, 12, 32, 16.0, "16", None):
            with self.subTest(value=value), self.assertRaises(image_io.InputError):
                cinegrade.render(self.source, self.root / "bad", assume_srgb=True, bit_depth=value)
        self.assertFalse((self.root / "bad").exists())

    def test_cli_fresh_processes_have_identical_png_bytes(self):
        outputs = []
        for name in ("cli-a", "cli-b"):
            proc = subprocess.run([sys.executable, "-B", str(HERE / "cinegrade.py"), "render", str(self.source),
                                   "--output", str(self.root / name), "--assume-srgb", "--bit-depth", "16"],
                                  capture_output=True, text=True, timeout=30)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            summary = json.loads(proc.stdout)
            self.assertIn("16bit_container_from_8bit_grade_no_added_precision", summary["warnings"])
            self.assertNotIn(str(self.root), proc.stdout)
            outputs.append((self.root / name / "render.png").read_bytes())
        self.assertEqual(outputs[0], outputs[1])
        decode_rgb16(outputs[0])

    def test_cli_invalid_depth_is_actionable(self):
        for value in ("12", "16.0", "invalid"):
            proc = subprocess.run([sys.executable, "-B", str(HERE / "cinegrade.py"), "render", str(self.source),
                                   "--output", str(self.root / "bad"), "--assume-srgb", "--bit-depth", value],
                                  capture_output=True, text=True, timeout=30)
            self.assertEqual(proc.returncode, 2)
            self.assertIn("--bit-depth", proc.stderr)
            self.assertNotIn("Traceback", proc.stderr)
        self.assertFalse((self.root / "bad").exists())

    def test_default_and_explicit_8bit_output_remain_rgb8(self):
        for name, options in (("default", {}), ("explicit8", {"bit_depth": 8})):
            report = cinegrade.render(self.source, self.root / name, assume_srgb=True, **options)
            blob = (self.root / name / "render.png").read_bytes()
            self.assertEqual(blob[24], 8)
            self.assertNotIn("precision", report["output"])
            self.assertNotIn("16bit_container_from_8bit_grade_no_added_precision", report["qa"]["warnings"])
            with Image.open(io.BytesIO(blob)) as output:
                expected, _ = cinegrade.grade_pixels(self.image, cinegrade.load_looks()["warm-muted"], 60)
                self.assertEqual(output.tobytes(), expected.tobytes())

    def test_jpeg_source_behavior_preserved(self):
        self.image.save(self.source, format="JPEG")
        decoded = image_io.load_image(self.source, assume_srgb=True).image
        report = self.render(strength=0)
        actual, _ = decode_rgb16((self.root / "out/render.png").read_bytes())
        np.testing.assert_array_equal(actual, np.asarray(decoded).astype(np.uint16) * 257)
        self.assertEqual(report["input"]["source_format"], "JPEG")

    def test_16bit_source_remains_rejected_without_silent_downconversion(self):
        self.source.write_bytes(srgb16.encode_png16(self.rgb.astype(np.uint16) * 257))
        with self.assertRaisesRegex(image_io.InputError, "8-bit sample depth"):
            self.render()
        self.assertFalse((self.root / "out").exists())


if __name__ == "__main__":
    unittest.main(verbosity=2)
