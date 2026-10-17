# SYNTHETIC mathematical fixtures, constructed solely for numeric tests.
# Ramps, pixels, patch sizes, dither and seeds are not real photographs or
# user-confirmed creative settings. Only 0.35 LSB comes from plan 3.5.
import json
import math
import unittest
import numpy as np
import banding_qa as b
import color_core as color
from image_io import InputError

class BandingQATests(unittest.TestCase):
    def pair(self, shape=(4, 4, 3)):
        pixels = np.full(shape, 128, dtype=np.uint8)
        return pixels.astype(np.float64) / 255, pixels

    def qa(self, before=None, before8=None, after=None, after8=None, patch_size=2):
        ref, pix = self.pair()
        return b.quantization_banding_qa(
            ref if before is None else before, pix if before8 is None else before8,
            ref if after is None else after, pix if after8 is None else after8,
            patch_size=patch_size)

    def test_identity(self):
        q = self.qa()
        for key in ("before_rms_lsb", "after_rms_lsb", "increase_lsb"):
            self.assertEqual(q[key], 0)
        self.assertEqual(q["warnings"], [])
        self.assertTrue(q["human_review_required"])
        self.assertNotIn("pass", q)

    def test_half_code_residual(self):
        q = self.qa(after=np.full((4, 4, 3), 127.5 / 255))
        self.assertAlmostEqual(q["after_rms_lsb"], 0.5)
        self.assertAlmostEqual(q["increase_lsb"], 0.5)
        self.assertEqual(q["warnings"], [b.WARNING])

    def test_source_error_subtracted(self):
        q = self.qa(before=np.full((4, 4, 3), 128.25 / 255),
                    after=np.full((4, 4, 3), 127.5 / 255))
        self.assertAlmostEqual(q["before_rms_lsb"], 0.25)
        self.assertAlmostEqual(q["increase_lsb"], 0.25)
        self.assertEqual(q["warnings"], [])

    def test_decrease_is_signed(self):
        q = self.qa(before=np.full((4, 4, 3), 127.5 / 255))
        self.assertAlmostEqual(q["increase_lsb"], -0.5)
        self.assertEqual(q["warnings"], [])

    def test_channel_pooling_without_cancellation(self):
        # Deliberately altered SYNTHETIC codes, not a nearest-quantizer recipe.
        pix = np.empty((4, 4, 3), dtype=np.uint8)
        pix[:] = [127, 128, 129]
        q = self.qa(after8=pix)
        self.assertAlmostEqual(q["after_rms_lsb"], math.sqrt(2 / 3))
        self.assertEqual(q["region"]["pixels_measured"], 4)
        self.assertEqual(q["region"]["channel_samples_measured"], 12)

    def test_strict_threshold(self):
        self.assertEqual(b.WARNING_THRESHOLD_LSB, 0.35)
        self.assertEqual(b._warnings(0.35), [])
        self.assertEqual(b._warnings(np.nextafter(0.35, 0)), [])
        self.assertEqual(b._warnings(np.nextafter(0.35, 1)), [b.WARNING])

    def test_source_selects_same_region_before_after(self):
        ref, _ = self.pair()
        check = np.array([[0, 1], [1, 0]])[..., None]
        ref[:2, :2] = check
        ref[:2, 2:] = check
        ref[2:, :2] = check
        pix = np.floor(ref * 255 + 0.5).astype(np.uint8)
        after = ref.copy()
        after[2:, 2:] = 127.5 / 255
        q = self.qa(before=ref, before8=pix, after=after, after8=pix)
        self.assertEqual(q["region"]["box_xywh"], [2, 2, 2, 2])
        self.assertEqual(q["region"]["source_smoothness_mean_square_encoded_srgb"], 0)
        self.assertAlmostEqual(q["increase_lsb"], 0.5)

    def test_ties_use_raster_order(self):
        q = self.qa()
        self.assertEqual(q["region"]["box_xywh"], [0, 0, 2, 2])
        self.assertEqual(q["region"]["tiles_examined"], 4)
        self.assertEqual(q["region"]["tie_break"], "first_in_raster_order")

    def test_unselected_region_is_not_claimed_measured(self):
        ref, pix = self.pair()
        altered = pix.copy()
        altered[2:, 2:] = 0
        q = self.qa(after8=altered)
        self.assertEqual(q["after_rms_lsb"], 0)
        self.assertIn("unselected_tiles_and_incomplete_edge_tiles_are_not_assessed", q["limitations"])

    def test_edges_reported_excluded(self):
        ref, pix = self.pair((5, 7, 3))
        q = self.qa(ref, pix, ref, pix, patch_size=3)
        self.assertEqual(q["region"]["tiles_examined"], 2)
        self.assertEqual(q["region"]["pixels_examined"], 18)
        self.assertEqual(q["region"]["pixels_excluded_at_right_and_bottom"], 17)

    def test_gradient_energy_by_hand(self):
        ref = np.array([[0, 0.25], [0.5, 0.75]])[..., None].repeat(3, axis=2)
        pix = np.floor(ref * 255 + 0.5).astype(np.uint8)
        q = self.qa(ref, pix, ref, pix)
        self.assertEqual(q["region"]["source_smoothness_mean_square_encoded_srgb"], (0.25**2 + 0.5**2) / 2)

    def test_patch_size_required_and_validated(self):
        ref, pix = self.pair()
        with self.assertRaises(TypeError):
            b.quantization_banding_qa(ref, pix, ref, pix)
        for size in (None, True, 0, 1, 5, -2, 2.0, "2", np.int64(2)):
            with self.subTest(size=size), self.assertRaises(InputError):
                self.qa(patch_size=size)

    def test_bad_reference_values(self):
        for value in (float("nan"), float("inf"), -0.01, 1.01):
            ref, _ = self.pair()
            ref[0, 0, 0] = value
            with self.subTest(value=value), self.assertRaises(InputError):
                self.qa(before=ref)
            with self.assertRaises(InputError):
                self.qa(after=ref)

    def test_references_require_real_float_images(self):
        for value in (np.zeros((4, 4, 3), dtype=np.uint8),
                      np.zeros((4, 4, 3), dtype=complex),
                      np.zeros((4, 4, 3), dtype=bool), [[0], [0, 1]],
                      np.empty((0, 4, 3)), np.zeros((4, 4)), np.zeros((4, 4, 4))):
            with self.subTest(value_type=type(value)), self.assertRaises(InputError):
                self.qa(before=value)

    def test_quantized_dtype_and_shape(self):
        for value in (np.zeros((4, 4, 3)), np.zeros((4, 4, 3), dtype=np.uint16),
                      np.zeros((3, 4, 3), dtype=np.uint8), [[0], [0, 1]]):
            with self.subTest(value_type=type(value)), self.assertRaises(InputError):
                self.qa(before8=value)
            with self.assertRaises(InputError):
                self.qa(after8=value)

    def test_reference_shapes_must_match(self):
        with self.assertRaises(InputError):
            self.qa(after=np.zeros((2, 4, 3)))
        ref, pix = self.pair((1, 4, 3))
        with self.assertRaises(InputError):
            self.qa(ref, pix, ref, pix)

    def test_readonly_strided_inputs_not_modified(self):
        ref, pix = self.pair((8, 8, 3))
        ref = ref[::2, ::2]
        pix = pix[::2, ::2]
        ref.setflags(write=False)
        pix.setflags(write=False)
        before = (ref.tobytes(), pix.tobytes())
        q = self.qa(ref, pix, ref, pix)
        self.assertEqual(q, self.qa(ref, pix, ref, pix))
        self.assertEqual(before, (ref.tobytes(), pix.tobytes()))

    def test_json_and_provenance_limitations(self):
        q = self.qa()
        self.assertEqual(json.loads(json.dumps(q, allow_nan=False)), q)
        self.assertEqual(q["units"], "8_bit_code_values")
        self.assertIn("caller_supplied", q["scope"])
        self.assertIn("does_not_recover_unknown_source_quantization_error", q["limitations"])
        self.assertIn("rms_does_not_measure_error_spatial_correlation_or_perceptual_banding", q["limitations"])
        self.assertEqual(q["region"]["selection_status"], "engineering_definition_not_photographer_validated")

    def test_real_quantizer_integration_against_scalar_residual(self):
        # SYNTHETIC smooth ramp and test-only dither, not a creative preset.
        ref = np.linspace(0.1, 0.9, 16).reshape(4, 4, 1).repeat(3, axis=2)
        before8 = color.quantize_srgb8(ref, amplitude_lsb=0, seed=0)
        after8 = color.quantize_srgb8(ref, amplitude_lsb=1, seed=7)
        q = self.qa(ref, before8, ref, after8, patch_size=4)
        def scalar(pixels):
            errors = [float(p) - 255 * float(r) for p, r in zip(pixels.flat, ref.flat)]
            return math.sqrt(math.fsum(e * e for e in errors) / len(errors))
        self.assertAlmostEqual(q["before_rms_lsb"], scalar(before8), places=14)
        self.assertAlmostEqual(q["after_rms_lsb"], scalar(after8), places=14)
        self.assertAlmostEqual(q["increase_lsb"], scalar(after8) - scalar(before8), places=14)

    def test_whole_patch_minimum_dimensions(self):
        ref, pix = self.pair((2, 2, 3))
        q = self.qa(ref, pix, ref, pix)
        self.assertEqual(q["region"]["tiles_examined"], 1)
        self.assertEqual(q["region"]["pixels_excluded_at_right_and_bottom"], 0)

if __name__ == "__main__":
    unittest.main()
