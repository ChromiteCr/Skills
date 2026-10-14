# SYNTHETIC mathematical fixtures only. Values, grid sizes, seeds and tolerances
# are test choices, NOT observed photos or photographer-confirmed look recipes.
# Gaussian references below use independent scalar math and explicit boundary indexing.
import inspect
import json
import math
import unittest
from unittest import mock

import numpy as np
import color_core as core


PARAMS = dict(threshold=0.5, sigma_fraction=0.125, truncate=2.0, strength=0.5)
Y_WEIGHTS = (87098/409605, 175762/245763, 12673/175545)


def reflected(i, n):
    if n == 1:
        return 0
    j = i % (2*n-2)
    return j if j < n else 2*n-2-j


def reference(rgb, *, threshold, sigma_fraction, truncate, strength):
    h, w, _ = rgb.shape
    sigma = min(h, w)*sigma_fraction
    radius = max(1, math.ceil(truncate*sigma))
    offsets = list(range(-radius, radius+1))
    kernel = [math.exp(-0.5*(k/sigma)**2) for k in offsets]
    normalizer = math.fsum(kernel)
    kernel = [v/normalizer for v in kernel]
    extracted = np.zeros(rgb.shape)
    for y in range(h):
        for x in range(w):
            lum = math.fsum(float(rgb[y,x,c])*Y_WEIGHTS[c] for c in range(3))
            if lum > threshold:
                extracted[y,x] = rgb[y,x]*((lum-threshold)/lum)
    expected = rgb.copy()
    for y in range(h):
        for x in range(w):
            for c in range(3):
                contribution = math.fsum(
                    kernel[j]*kernel[i]*extracted[reflected(y+dy,h),reflected(x+dx,w),c]
                    for j,dy in enumerate(offsets) for i,dx in enumerate(offsets))
                expected[y,x,c] += strength*contribution
    return expected


class BloomTests(unittest.TestCase):
    def bloom(self, rgb, **changes):
        return core.bloom_linear_srgb(rgb, **(PARAMS | changes))

    def test_constant_hand_calculation(self):
        rgb = np.full((8,10,3), 0.75)
        out, qa = self.bloom(rgb)
        np.testing.assert_allclose(out, 0.875, rtol=0, atol=3e-16)
        self.assertEqual(qa["highlight_pixels"], 80)
        self.assertEqual(qa["pixels_total"], 80)

    def test_impulse_matches_independent_gaussian(self):
        rgb = np.zeros((9,11,3)); rgb[4,5] = 1
        out, _ = self.bloom(rgb)
        np.testing.assert_allclose(out, reference(rgb, **PARAMS), rtol=2e-15, atol=2e-16)
        self.assertGreater(out[4,6,0], 0)
        self.assertGreater(out[4,5,0], 1)

    def test_boundary_reflection_matches_scalar_reference(self):
        rgb = np.arange(36, dtype=float).reshape(3,4,3)/35
        params = PARAMS | dict(threshold=0.1, sigma_fraction=0.3)
        out, _ = core.bloom_linear_srgb(rgb, **params)
        np.testing.assert_allclose(out, reference(rgb, **params), rtol=3e-15, atol=3e-16)

    def test_zero_strength_is_independent_exact_copy(self):
        rgb = np.arange(72, dtype=float).reshape(4,6,3)/71
        out, qa = self.bloom(rgb, strength=0)
        np.testing.assert_array_equal(out, rgb)
        self.assertFalse(np.shares_memory(out, rgb))
        self.assertFalse(qa["blur_performed"])
        self.assertEqual(qa["changed_pixels"], 0)

    def test_no_highlights_identity_including_threshold(self):
        rgb = np.full((4,5,3), 0.5)
        out, qa = self.bloom(rgb)
        np.testing.assert_array_equal(out, rgb)
        self.assertEqual(qa["highlight_pixels"], 0)
        self.assertIn("no_highlights_above_threshold", qa["warnings"])
        self.assertFalse(qa["blur_performed"])

    def test_all_black_and_white_threshold_one(self):
        for rgb, threshold in ((np.zeros((2,3,3)), 0), (np.ones((2,3,3)), 1)):
            with self.subTest(threshold=threshold):
                out, _ = self.bloom(rgb, threshold=threshold)
                np.testing.assert_array_equal(out, rgb)

    def test_readonly_fortran_and_reversed_arrays(self):
        rgb = np.linspace(0,1,72).reshape(4,6,3)
        for value in (np.asfortranarray(rgb), rgb[:,::-1], rgb.transpose(1,0,2)):
            value.setflags(write=False)
            before = value.copy()
            out, _ = self.bloom(value)
            reference_out, _ = self.bloom(np.array(value, order="C"))
            np.testing.assert_array_equal(out, reference_out)
            np.testing.assert_array_equal(value, before)
            self.assertEqual(out.dtype, np.float64)
            self.assertFalse(np.shares_memory(out, value))

    def test_sigma_and_support_follow_short_side(self):
        for shape, sigma, radius in (((8,20,3),1,2), ((20,8,3),1,2), ((16,40,3),2,4)):
            out, qa = self.bloom(np.full(shape,0.75))
            self.assertEqual(out.shape, shape)
            self.assertEqual(qa["sigma_pixels"], sigma)
            self.assertEqual(qa["kernel_radius_pixels"], radius)
            self.assertEqual(qa["border"], "reflect101")

    def test_spatial_symmetry(self):
        rgb = np.zeros((9,9,3)); rgb[4,4] = (0.9,0.8,0.7)
        out, _ = self.bloom(rgb)
        np.testing.assert_allclose(out, np.rot90(out), rtol=0, atol=2e-16)

    def test_channels_preserve_source_color_order(self):
        rgb = np.zeros((7,7,3)); rgb[3,3] = (1,0.5,0.25)
        out, _ = self.bloom(rgb, threshold=0)
        self.assertGreater(out[3,4,0], 0)
        np.testing.assert_allclose(out[3,4], out[3,4,0]*np.array([1,0.5,0.25]), rtol=0, atol=1e-17)

    def test_selection_uses_linear_srgb_luminance(self):
        rgb = np.array([[[1,0,0], [0,1,0], [0,0,1]]], dtype=float)
        out, qa = self.bloom(rgb, threshold=0.25)
        self.assertEqual(qa["highlight_pixels"], 1)
        np.testing.assert_array_equal(out[...,0], rgb[...,0])
        np.testing.assert_array_equal(out[...,2], rgb[...,2])
        self.assertGreater(out[0,1,1], 1)

    def test_strength_is_linear_and_monotone(self):
        rgb = np.full((4,5,3),0.7)
        full, _ = self.bloom(rgb, strength=1)
        half, _ = self.bloom(rgb, strength=0.5)
        np.testing.assert_allclose(half-rgb, (full-rgb)/2, rtol=0, atol=2e-16)
        self.assertTrue(np.all(full >= half))
        self.assertTrue(np.all(half >= rgb))

    def test_higher_threshold_reduces_bloom(self):
        rgb = np.linspace(0,1,90).reshape(5,6,3)
        low, _ = self.bloom(rgb, threshold=0.1)
        high, _ = self.bloom(rgb, threshold=0.8)
        self.assertTrue(np.all(low >= high))
        self.assertTrue(np.all(high >= rgb))

    def test_overrange_is_returned_and_counted_not_clipped(self):
        rgb = np.ones((4,5,3))
        out, qa = self.bloom(rgb, threshold=0)
        np.testing.assert_allclose(out,1.5,rtol=0,atol=3e-16)
        self.assertEqual(qa["pixels_above_one"],20)
        self.assertEqual(qa["changed_pixels"],20)
        self.assertIn("linear_output_above_one_requires_explicit_tone_handling",qa["warnings"])
        self.assertNotIn("pass",qa)

    def test_finite_support_does_not_wrap_edges(self):
        rgb = np.zeros((16,20,3)); rgb[8,10]=1
        out, qa = self.bloom(rgb, sigma_fraction=1/16, truncate=2)
        self.assertEqual(qa["kernel_radius_pixels"],2)
        np.testing.assert_array_equal(out[:6],rgb[:6])
        np.testing.assert_array_equal(out[11:],rgb[11:])
        np.testing.assert_array_equal(out[:,:8],rgb[:,:8])
        np.testing.assert_array_equal(out[:,13:],rgb[:,13:])

    def test_invalid_image_coordinates_rejected(self):
        for rgb in (0, [], [0,0,0], np.zeros((3,3)), np.zeros((2,2,4)),
                    np.zeros((1,2,2,3)), np.zeros((0,3,3)), [[[True]*3]],
                    [[["0"]*3]], [[[1j]*3]], [[[float("nan")]*3]],
                    [[[float("inf")]*3]], [[[-1e-20]*3]], [[[1.0000000000000002]*3]]):
            with self.subTest(shape=np.shape(rgb)), self.assertRaises(ValueError):
                self.bloom(rgb)

    def test_parameters_are_required_and_strict(self):
        signature = inspect.signature(core.bloom_linear_srgb)
        for name in PARAMS:
            self.assertIs(signature.parameters[name].default, inspect.Parameter.empty)
            for bad in (True, "0.5", None, float("nan"), float("inf"), -0.1):
                with self.subTest(name=name,bad=bad), self.assertRaises(ValueError):
                    self.bloom(np.ones((4,4,3)), **{name:bad})
        for name in ("threshold","sigma_fraction","strength"):
            with self.subTest(name=name), self.assertRaises(ValueError):
                self.bloom(np.ones((4,4,3)), **{name:1.1})
        for name in ("sigma_fraction","truncate"):
            with self.subTest(name=name), self.assertRaises(ValueError):
                self.bloom(np.ones((4,4,3)), **{name:0})

    def test_support_budget_is_rejected_not_silently_shortened(self):
        with self.assertRaises(ValueError):
            self.bloom(np.ones((4,4,3)), sigma_fraction=1, truncate=2)
        with self.assertRaises(ValueError):
            self.bloom(np.ones((4,4,3)), truncate=1e308)
        with self.assertRaises(ValueError):
            self.bloom(np.ones((4,4,3)), sigma_fraction=1, truncate=2,strength=0)

    def test_one_pixel_axes_and_tiny_sigma(self):
        for shape in ((1,1,3),(1,5,3),(5,1,3)):
            rgb = np.full(shape,0.75)
            out, _ = self.bloom(rgb)
            np.testing.assert_allclose(out,0.875,rtol=0,atol=3e-16)
        rgb = np.full((2,2,3),0.75)
        out, qa = self.bloom(rgb, sigma_fraction=np.nextafter(0.0,1.0))
        np.testing.assert_array_equal(out,np.full_like(rgb,0.875))
        self.assertEqual(qa["kernel_radius_pixels"],1)

    def test_repeatable_without_global_random_state(self):
        rgb = np.linspace(0,1,105).reshape(5,7,3)
        state = np.random.get_state()
        out1, qa1 = self.bloom(rgb)
        out2, qa2 = self.bloom(rgb)
        self.assertEqual(out1.tobytes(),out2.tobytes())
        self.assertEqual(json.dumps(qa1,sort_keys=True),json.dumps(qa2,sort_keys=True))
        after = np.random.get_state()
        self.assertEqual(state[0],after[0]); np.testing.assert_array_equal(state[1],after[1])
        self.assertEqual(state[2:],after[2:])

    def test_missing_backend_fails_only_when_blur_is_needed(self):
        rgb = np.full((4,4,3),0.75)
        with mock.patch.dict("sys.modules", {"cv2":None}):
            with self.assertRaisesRegex(ValueError,"OpenCV is required"):
                self.bloom(rgb)
            out, qa = self.bloom(rgb,strength=0)
            np.testing.assert_array_equal(out,rgb)
            self.assertIsNone(qa["opencv_version"])
            out, qa = self.bloom(rgb,threshold=1)
            np.testing.assert_array_equal(out,rgb)
            self.assertFalse(qa["blur_performed"])

    def test_encoded_input_is_not_implicitly_gamma_decoded(self):
        encoded = np.full((4,4,3),0.75)
        linear = core.srgb_to_linear(encoded)
        proper, _ = self.bloom(linear,threshold=0.25)
        wrong, _ = self.bloom(encoded,threshold=0.25)
        self.assertGreater(float(np.max(np.abs(core.linear_to_srgb(proper)-wrong))),0.01)

    def test_existing_color_path_to_quantization(self):
        rgb8 = np.zeros((9,9,3),dtype=np.uint8); rgb8[4,4]=(180,190,200)
        linear = core.srgb_to_linear(rgb8.astype(float)/255)
        lab = core.contrast_oklab(core.linear_srgb_to_oklab(linear),contrast=1,strength=0)
        mapped, _ = core.gamut_map_linear_srgb(core.oklab_to_linear_srgb(lab))
        bloomed, qa = self.bloom(mapped,threshold=0.25,strength=0.25)
        self.assertEqual(qa["pixels_above_one"],0)
        final = core.quantize_srgb8(core.linear_to_srgb(bloomed),amplitude_lsb=0,seed=0)
        self.assertEqual(final.shape,rgb8.shape)
        self.assertTrue(np.any(final[3:6,3:6] > rgb8[3:6,3:6]))


if __name__ == "__main__":
    unittest.main(verbosity=2)
