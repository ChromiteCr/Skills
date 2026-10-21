# SYNTHETIC fixtures only: constructed code ramps, colors, metadata and malformed
# files. These are software/math probes, not photographs, observed scene data,
# or user-confirmed creative settings. PNG encoding below is an independent
# test fixture builder, not the production exporter/decoder under test.
import hashlib
import io
import json
from pathlib import Path
import struct
import tempfile
import unittest
from unittest import mock
import zlib

import numpy as np
from PIL import Image, ImageCms

import color_core
import float_image_io as fio
import image_io
import srgb16

HERE = Path(__file__).resolve().parent


def chunk(kind, payload):
    return struct.pack(">I", len(payload)) + kind + payload + struct.pack(">I", zlib.crc32(kind + payload))


def pack(chunks):
    return b"\x89PNG\r\n\x1a\n" + b"".join(chunk(k, p) for k, p in chunks)


def fixture(samples, filters=(0,), before=(), after=(), header=None, raw=None):
    height, width, _ = samples.shape
    ihdr = struct.pack(">IIBBBBB", width, height, 16, 2, 0, 0, 0) if header is None else header
    if raw is None:
        rows = []
        previous = bytes(width * 6)
        for y, values in enumerate(samples):
            row = struct.pack(">" + "H" * (3 * width), *map(int, values.flat))
            method = filters[y % len(filters)]
            encoded = []
            for i, value in enumerate(row):
                left = row[i - 6] if i >= 6 else 0
                above = previous[i]
                upper_left = previous[i - 6] if i >= 6 else 0
                if method == 0:
                    prediction = 0
                elif method == 1:
                    prediction = left
                elif method == 2:
                    prediction = above
                elif method == 3:
                    prediction = (left + above) // 2
                else:
                    estimate = left + above - upper_left
                    # Independent stable minimization pins Paeth tie order.
                    prediction = min((left, above, upper_left), key=lambda v: abs(v - estimate))
                encoded.append((value - prediction) % 256)
            rows.append(bytes([method]) + bytes(encoded))
            previous = row
        raw = b"".join(rows)
    return [(b"IHDR", ihdr), *before, (b"IDAT", zlib.compress(raw)), *after, (b"IEND", b"")]


class FloatInputTests(unittest.TestCase):
    def setUp(self):
        local = HERE.parents[3] / ".git"
        temp = tempfile.TemporaryDirectory(prefix="synthetic-input16-", dir=local if local.is_dir() else HERE)
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.source = self.root / "SYNTHETIC_PRIVATE_SOURCE.png"
        self.samples = np.array([[[0, 1, 255], [256, 257, 258], [32767, 32768, 32769]],
                                 [[65535, 65534, 65400], [700, 900, 1100], [30000, 40000, 50000]]], dtype=np.uint16)

    def load(self, chunks=None, **kwargs):
        self.source.write_bytes(pack(fixture(self.samples) if chunks is None else chunks))
        return fio.load_float_image(self.source, **kwargs)

    def assert_bad(self, chunks, **kwargs):
        with self.assertRaises(image_io.InputError):
            self.load(chunks, assume_srgb=True, **kwargs)

    def test_all_65536_codes_are_retained(self):
        codes = np.arange(65536, dtype=np.uint16).reshape(256, 256)
        samples = np.stack((codes, codes[::-1], codes[:, ::-1]), axis=-1)
        loaded = self.load(fixture(samples), assume_srgb=True)
        self.assertEqual(loaded.encoded_srgb.dtype, np.float64)
        np.testing.assert_array_equal(srgb16.quantize_srgb16(loaded.encoded_srgb), samples)
        self.assertEqual(np.unique(loaded.encoded_srgb[..., 0]).size, 65536)
        self.assertEqual(loaded.provenance["source_bit_depth"], 16)

    def test_low_bytes_not_discarded(self):
        samples = np.arange(256, 512, dtype=np.uint16).reshape(1, 256, 1).repeat(3, axis=2)
        loaded = self.load(fixture(samples), assume_srgb=True)
        self.assertEqual(np.unique(loaded.encoded_srgb).size, 256)
        self.assertTrue(np.all(np.diff(loaded.encoded_srgb[0, :, 0]) > 0))
        np.testing.assert_array_equal(loaded.encoded_srgb, samples.astype(float) / 65535)

    def test_floating_color_roundtrip_and_16bit_export(self):
        # Synthetic identity color roundtrip through the EXISTING float core.
        # No invented look/strength, no assertion of photographic acceptance.
        samples = (np.arange(3072, dtype=np.uint16).reshape(4, 256, 3) + 1) * 19
        loaded = self.load(fixture(samples), assume_srgb=True)
        original = loaded.encoded_srgb.copy()
        linear = color_core.srgb_to_linear(original)
        lab = color_core.linear_srgb_to_oklab(linear)
        restored = color_core.linear_to_srgb(color_core.oklab_to_linear_srgb(lab))
        # Only roundoff at exact gamut endpoints can fall outside the exporter
        # domain; this fixture deliberately stays strictly inside both endpoints.
        output = srgb16.quantize_srgb16(restored)
        np.testing.assert_array_equal(output, samples)
        destination = self.root / "roundtrip.png"
        destination.write_bytes(srgb16.encode_png16(output))
        reread = fio.load_float_image(destination)
        np.testing.assert_array_equal(reread.encoded_srgb, original)
        self.assertGreater(np.unique(output[..., 0]).size, 256)
        np.testing.assert_array_equal(loaded.encoded_srgb, original)

    def test_all_filters_and_mixed_scanlines(self):
        # Fixed-seed random bytes stress overflow, high/low lanes and Paeth ties.
        rng = np.random.default_rng(621)
        samples = rng.integers(0, 65536, size=(11, 17, 3), dtype=np.uint16)
        for filters in ((0,), (1,), (2,), (3,), (4,), (0, 1, 2, 3, 4)):
            with self.subTest(filters=filters):
                data = fixture(samples, filters=filters)
                loaded = self.load(data, assume_srgb=True)
                np.testing.assert_array_equal(srgb16.quantize_srgb16(loaded.encoded_srgb), samples)
                # Pillow is a SECONDARY structural decoder only, not a 16-bit
                # precision oracle. It exposes the expected high bytes as RGB8.
                with Image.open(io.BytesIO(pack(data))) as opened:
                    np.testing.assert_array_equal(np.asarray(opened), samples >> 8)

    def test_single_pixel_and_narrow_scanlines(self):
        for samples in (self.samples[:1, :1], self.samples[:, :1], self.samples[:1]):
            for filters in ((1,), (2,), (3,), (4,)):
                with self.subTest(shape=samples.shape, filters=filters):
                    loaded = self.load(fixture(samples, filters), assume_srgb=True)
                    np.testing.assert_array_equal(srgb16.quantize_srgb16(loaded.encoded_srgb), samples)

    def test_consecutive_split_idat(self):
        chunks = fixture(self.samples)
        payload = chunks[1][1]
        parts = [(b"IDAT", b""), *[(b"IDAT", bytes([v])) for v in payload], (b"IDAT", b"")]
        loaded = self.load([chunks[0], *parts, chunks[-1]], assume_srgb=True)
        np.testing.assert_array_equal(srgb16.quantize_srgb16(loaded.encoded_srgb), self.samples)

    def test_bundled_profile_is_verified_without_rgb8_conversion(self):
        self.source.write_bytes(srgb16.encode_png16(self.samples))
        with mock.patch.object(ImageCms, "profileToProfile", side_effect=AssertionError("no RGB8 conversion")), mock.patch.object(Image, "open", side_effect=AssertionError("no RGB8 decoder")):
            loaded = fio.load_float_image(self.source)
        np.testing.assert_array_equal(srgb16.quantize_srgb16(loaded.encoded_srgb), self.samples)
        color = loaded.provenance["color_management"]
        self.assertEqual(color["action"], "verified_srgb_icc_identity")
        self.assertEqual(color["source_icc_sha256"], srgb16.PROFILE_SHA256)

    def test_missing_profile_requires_explicit_confirmation(self):
        with self.assertRaisesRegex(image_io.InputError, "confirm sRGB explicitly"):
            self.load()
        loaded = self.load(assume_srgb=True)
        self.assertEqual(loaded.provenance["color_management"]["action"], "explicit_srgb_assumption")
        self.assertIn("untagged_source_assumed_srgb", loaded.provenance["warnings"])

    def test_nonmatching_profiles_never_fall_back_to_assumption(self):
        lab = ImageCms.ImageCmsProfile(ImageCms.createProfile("LAB")).tobytes()
        mutated = bytearray(srgb16.PROFILE.read_bytes())
        mutated[-1] ^= 1
        for profile in (lab, bytes(mutated), b"SYNTHETIC invalid ICC", b""):
            with self.subTest(length=len(profile)):
                self.assert_bad(fixture(self.samples, before=[(b"iCCP", b"sRGB\0\0" + zlib.compress(profile))]))

    def test_profile_stream_is_bounded(self):
        profile = b"SYNTHETIC" * 100
        with mock.patch.object(fio, "MAX_ICC_BYTES", 32):
            self.assert_bad(fixture(self.samples, before=[(b"iCCP", b"sRGB\0\0" + zlib.compress(profile))]))

    def test_malformed_icc_containers(self):
        for payload in (b"", b"\0\0x", b"x\0\1x", b"x\0\0broken", b" bad\0\0x", b"bad  name\0\0x", b"a" * 80 + b"\0\0x"):
            with self.subTest(payload=payload[:12]):
                self.assert_bad(fixture(self.samples, before=[(b"iCCP", payload)]))

    def test_conflicting_or_malformed_color_signals(self):
        for metadata in ([(b"gAMA", struct.pack(">I", 100000))], [(b"gAMA", b"x")],
                         [(b"gAMA", bytes(4))], [(b"cHRM", bytes(32))],
                         [(b"cHRM", b"x")], [(b"sRGB", b"\4")], [(b"sRGB", b"")],
                         [(b"sRGB", b"\0"), (b"cHRM", bytes(32))]):
            with self.subTest(metadata=metadata):
                self.assert_bad(fixture(self.samples, before=metadata))

    def test_standard_srgb_signals_with_confirmation(self):
        chroma = struct.pack(">8I", 31270, 32900, 64000, 33000, 30000, 60000, 15000, 6000)
        metadata = [(b"sRGB", b"\0"), (b"gAMA", struct.pack(">I", 45455)), (b"cHRM", chroma)]
        loaded = self.load(fixture(self.samples, before=metadata), assume_srgb=True)
        np.testing.assert_array_equal(srgb16.quantize_srgb16(loaded.encoded_srgb), self.samples)

    def test_srgb_and_icc_combination_rejected(self):
        metadata = [(b"sRGB", b"\0"), (b"iCCP", b"sRGB\0\0" + zlib.compress(srgb16.PROFILE.read_bytes()))]
        self.assert_bad(fixture(self.samples, before=metadata))

    def test_all_eight_orientations_preserve_samples(self):
        # Hand-enumerated EXIF arrangements, independent of production transforms.
        arrangements = {1: [[0, 1, 2], [3, 4, 5]], 2: [[2, 1, 0], [5, 4, 3]],
                        3: [[5, 4, 3], [2, 1, 0]], 4: [[3, 4, 5], [0, 1, 2]],
                        5: [[0, 3], [1, 4], [2, 5]], 6: [[3, 0], [4, 1], [5, 2]],
                        7: [[5, 2], [4, 1], [3, 0]], 8: [[2, 5], [1, 4], [0, 3]]}
        for orientation, indices in arrangements.items():
            with self.subTest(orientation=orientation):
                exif = Image.Exif()
                exif[274] = orientation
                loaded = self.load(fixture(self.samples, before=[(b"eXIf", exif.tobytes()[6:])]), assume_srgb=True)
                expected = self.samples.reshape(6, 3)[indices]
                np.testing.assert_array_equal(srgb16.quantize_srgb16(loaded.encoded_srgb), expected)
                self.assertEqual(loaded.provenance["oriented_dimensions"], [expected.shape[1], expected.shape[0]])
                self.assertEqual(loaded.provenance["orientation_applied"], orientation)

    def test_private_metadata_is_not_returned(self):
        exif = Image.Exif()
        exif[274] = 6
        exif[34855] = 200  # SYNTHETIC technical EXIF probe, not a camera reading.
        exif[271] = "SYNTHETIC_PRIVATE_CAMERA"
        exif[42033] = "SYNTHETIC_PRIVATE_SERIAL"
        extra = [(b"eXIf", exif.tobytes()[6:]), (b"tEXt", b"Comment\0SYNTHETIC_PRIVATE_COMMENT")]
        loaded = self.load(fixture(self.samples, after=extra), assume_srgb=True)
        text = json.dumps(loaded.provenance, allow_nan=False)
        self.assertNotIn("SYNTHETIC_PRIVATE", text)
        self.assertNotIn(str(self.source), text)
        self.assertEqual(loaded.provenance["technical_exif"], {"iso": 200.0})

    def test_invalid_exif_and_orientation_rejected(self):
        exif = Image.Exif()
        exif[274] = 9
        for payload in (b"broken", b"II\x2a\x00", exif.tobytes()[6:]):
            with self.subTest(length=len(payload)):
                self.assert_bad(fixture(self.samples, before=[(b"eXIf", payload)]))

    def test_source_unchanged_and_no_outputs_created(self):
        self.source.write_bytes(pack(fixture(self.samples)))
        before = self.source.read_bytes()
        files = list(self.root.iterdir())
        loaded = fio.load_float_image(self.source, assume_srgb=True)
        self.assertEqual(self.source.read_bytes(), before)
        self.assertEqual(list(self.root.iterdir()), files)
        self.assertEqual(loaded.provenance["source_sha256"], hashlib.sha256(before).hexdigest())

    def test_single_snapshot_read_for_both_depths(self):
        for depth in (8, 16):
            with self.subTest(depth=depth):
                if depth == 8:
                    stream = io.BytesIO()
                    Image.new("RGB", (3, 2), (1, 2, 3)).save(stream, format="PNG")
                    blob = stream.getvalue()
                else:
                    blob = pack(fixture(self.samples))
                with mock.patch.object(image_io, "_read_source", return_value=blob) as reader:
                    loaded = fio.load_float_image(self.source, assume_srgb=True)
                reader.assert_called_once_with(self.source)
                self.assertEqual(loaded.provenance["source_sha256"], hashlib.sha256(blob).hexdigest())

    def test_8bit_jpeg_png_and_grayscale_share_legacy_decoder(self):
        for fmt in ("PNG", "JPEG"):
            for mode in ("RGB", "L"):
                with self.subTest(fmt=fmt, mode=mode):
                    image = Image.new(mode, (3, 2), (24, 128, 230) if mode == "RGB" else 128)
                    profile = ImageCms.ImageCmsProfile(ImageCms.createProfile("sRGB")).tobytes() if mode == "RGB" else None
                    image.save(self.source, format=fmt, icc_profile=profile)
                    expected = image_io.load_image(self.source, assume_srgb=True)
                    actual = fio.load_float_image(self.source, assume_srgb=True)
                    np.testing.assert_array_equal(actual.encoded_srgb, np.asarray(expected.image).astype(float) / 255)
                    for key, value in expected.provenance.items():
                        self.assertEqual(actual.provenance[key], value)
                    self.assertEqual(actual.provenance["source_bit_depth"], 8)

    def test_legacy_loader_still_refuses_rgb16(self):
        self.source.write_bytes(pack(fixture(self.samples)))
        with self.assertRaisesRegex(image_io.InputError, "no silent downconversion"):
            image_io.load_image(self.source, assume_srgb=True)

    def test_symlinks_directories_and_missing_inputs_rejected(self):
        self.source.write_bytes(pack(fixture(self.samples)))
        link = self.root / "alias.png"
        link.symlink_to(self.source)
        for path in (link, self.root, self.root / "missing.png"):
            with self.subTest(path=path.name), self.assertRaises(image_io.InputError):
                fio.load_float_image(path, assume_srgb=True)

    def test_compressed_source_and_pixel_bounds(self):
        self.source.write_bytes(pack(fixture(self.samples)))
        with mock.patch.object(image_io, "MAX_SOURCE_BYTES", 16), self.assertRaises(image_io.InputError):
            fio.load_float_image(self.source, assume_srgb=True)
        with mock.patch.object(fio, "MAX_PIXELS", 1), self.assertRaises(image_io.InputError):
            fio.load_float_image(self.source, assume_srgb=True)

    def test_unsupported_headers_fail_explicitly(self):
        for header in ((3, 2, 16, 2, 0, 0, 1), (3, 2, 16, 6, 0, 0, 0),
                       (3, 2, 16, 0, 0, 0, 0), (3, 2, 16, 2, 1, 0, 0),
                       (3, 2, 16, 2, 0, 1, 0), (0, 2, 16, 2, 0, 0, 0),
                       (2**31, 2, 16, 2, 0, 0, 0)):
            with self.subTest(header=header):
                self.assert_bad(fixture(self.samples, header=struct.pack(">IIBBBBB", *header)))

    def test_alpha_animation_hdr_and_unknown_critical_rejected(self):
        for kind in (b"tRNS", b"acTL", b"fcTL", b"fdAT", b"cICP", b"mDCv", b"cLLi", b"ABCD"):
            with self.subTest(kind=kind):
                self.assert_bad(fixture(self.samples, before=[(kind, b"\0" * 8)]))

    def test_duplicate_or_misordered_chunks_rejected(self):
        original = fixture(self.samples)
        for chunks in ([original[0], *original], original[1:] + original[:1],
                       [original[0], (b"sRGB", b"\0"), (b"sRGB", b"\0"), *original[1:]],
                       [*original[:-1], (b"gAMA", struct.pack(">I", 45455)), original[-1]],
                       [*original[:-1], (b"tEXt", b"a\0b"), original[1], original[-1]],
                       [original[0], original[-1]], original[:-1]):
            with self.subTest(kinds=[k for k, p in chunks]):
                self.assert_bad(chunks)

    def test_crc_truncation_and_trailing_bytes(self):
        blob = pack(fixture(self.samples))
        corrupt = bytearray(blob)
        corrupt[-1] ^= 1
        for bad in (bytes(corrupt), blob[:-1], blob[:-12], blob + b"extra", blob[:27]):
            with self.subTest(length=len(bad)):
                self.source.write_bytes(bad)
                with self.assertRaises(image_io.InputError):
                    fio.load_float_image(self.source, assume_srgb=True)

    def test_bad_chunk_names_and_reserved_bit(self):
        for kind in (b"test", b"te1t", b"\0EXt"):
            with self.subTest(kind=kind):
                self.assert_bad(fixture(self.samples, before=[(kind, b"")]))

    def test_scanline_filters_and_exact_decompressed_length(self):
        expected = self.samples.shape[0] * (self.samples.shape[1] * 6 + 1)
        for raw in (b"\5" + bytes(expected - 1), bytes(expected - 1), bytes(expected + 1), bytes(expected * 100)):
            with self.subTest(length=len(raw)):
                self.assert_bad(fixture(self.samples, raw=raw))

    def test_incomplete_trailing_and_concatenated_zlib_streams(self):
        chunks = fixture(self.samples)
        compressed = chunks[1][1]
        for bad in (compressed[:-1], compressed + b"tail", compressed + zlib.compress(b""), b"broken"):
            with self.subTest(length=len(bad)):
                self.assert_bad([chunks[0], (b"IDAT", bad), chunks[-1]])

    def test_optional_palette_validation(self):
        valid = self.load(fixture(self.samples, before=[(b"PLTE", bytes(6))]), assume_srgb=True)
        np.testing.assert_array_equal(srgb16.quantize_srgb16(valid.encoded_srgb), self.samples)
        for payload in (b"", b"x", bytes(771)):
            self.assert_bad(fixture(self.samples, before=[(b"PLTE", payload)]))

    def test_returned_arrays_are_independent(self):
        first = self.load(assume_srgb=True)
        second = fio.load_float_image(self.source, assume_srgb=True)
        self.assertFalse(np.shares_memory(first.encoded_srgb, second.encoded_srgb))
        first.encoded_srgb[:] = 0
        np.testing.assert_array_equal(srgb16.quantize_srgb16(second.encoded_srgb), self.samples)


if __name__ == "__main__":
    unittest.main()
