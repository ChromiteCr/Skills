# Synthetic mathematical fixtures only, not measured photographs or approved looks.
# Origin: sRGB transfer definition, published Oklab primary vectors, analytic curves.
# Grid/ramp values and contrast=2 are synthetic test choices, not user-confirmed recipes.
import unittest
import numpy as np
import color_core as core


class ColorCoreTests(unittest.TestCase):
    def close(self, actual, expected, atol=2e-14):
        np.testing.assert_allclose(actual, expected, rtol=0, atol=atol)

    def test_srgb_decode_reference_values(self):
        self.close(core.srgb_to_linear([0, 0.04045, 0.5, 1]),
                   [0, 0.0031308049535603713, 0.21404114048223255, 1])

    def test_srgb_encode_reference_values(self):
        self.close(core.linear_to_srgb([0, 0.0031308, 0.21404114048223255, 1]),
                   [0, 0.040449936, 0.5, 1])

    def test_all_rgb8_code_values_round_trip(self):
        encoded = np.arange(256, dtype=np.float64) / 255
        self.close(core.linear_to_srgb(core.srgb_to_linear(encoded)), encoded)

    def test_extended_signed_transfer_does_not_clip(self):
        encoded = np.array([-2, -1, -0.5, -0.02, 0, 0.02, 0.5, 1, 2])
        linear = core.srgb_to_linear(encoded)
        self.assertLess(linear[0], -1)
        self.assertGreater(linear[-1], 1)
        self.close(linear, -linear[::-1])
        self.close(core.linear_to_srgb(linear), encoded)

    def test_transfer_shape_dtype_scalar_and_no_mutation(self):
        source = np.array([[0, 0.5], [0.75, 1]], dtype=np.float32)
        before = source.copy()
        result = core.srgb_to_linear(source)
        self.assertEqual(result.shape, source.shape)
        self.assertEqual(result.dtype, np.float64)
        np.testing.assert_array_equal(source, before)
        self.assertEqual(core.srgb_to_linear(0.5).shape, ())

    def test_published_oklab_primary_vectors(self):
        # Rounded published linear-sRGB primary conversions (not computed by this module).
        # 5e-8 accommodates the eight decimal places of these reference vectors.
        self.close(core.linear_srgb_to_oklab(np.eye(3)),
                   [[0.62795536, 0.22486306, 0.12584630],
                    [0.86643961, -0.23388757, 0.17949848],
                    [0.45201372, -0.03245698, -0.31152815]], atol=5e-8)

    def test_black_white_and_gray_lightness(self):
        lab = core.linear_srgb_to_oklab([[0, 0, 0], [1, 1, 1], [0.125, 0.125, 0.125]])
        self.close(lab[0], [0, 0, 0], atol=0)
        self.close(lab[1], [1, 0, 0], atol=4e-8)
        self.close(lab[2], [0.5, 0, 0], atol=2e-8)

    def test_signed_cube_root_and_extended_gamut_round_trip(self):
        rgb = np.array([[-0.125] * 3, [-0.5, 0.8, 1.5], [2, -1, 0.3]])
        lab = core.linear_srgb_to_oklab(rgb)
        self.assertTrue(np.all(np.isfinite(lab)))
        self.assertLess(lab[0, 0], 0)
        self.close(core.oklab_to_linear_srgb(lab), rgb)
        self.close(core.linear_srgb_to_oklab(-rgb), -lab)

    def test_dense_synthetic_lattice_round_trip(self):
        # 17^3 points; includes negative and >1 coordinates to catch hidden clipping.
        axis = np.linspace(-0.25, 1.25, 17)
        rgb = np.stack(np.meshgrid(axis, axis, axis, indexing="ij"), axis=-1)
        before = rgb.copy()
        self.close(core.oklab_to_linear_srgb(core.linear_srgb_to_oklab(rgb)), rgb)
        np.testing.assert_array_equal(rgb, before)

    def test_triplet_and_image_shapes(self):
        for shape in ((3,), (2, 3), (2, 4, 3)):
            source = np.full(shape, 0.125)
            lab = core.linear_srgb_to_oklab(source)
            self.assertEqual(lab.shape, shape)
            self.close(core.oklab_to_linear_srgb(lab), source)

    def test_oklch_cardinal_hues_and_neutral_convention(self):
        lab = [[0.5, 1, 0], [0.5, 0, 1], [0.5, -1, 0], [0.5, 0, -1], [0.5, 0, 0]]
        self.close(core.oklab_to_oklch(lab),
                   [[0.5, 1, 0], [0.5, 1, 90], [0.5, 1, 180], [0.5, 1, 270], [0.5, 0, 0]])

    def test_oklch_round_trip_wrapped_hues_and_negative_chroma(self):
        lch = np.array([[0.5, 0.2, 0], [0.5, 0.2, 360], [0.5, 0.2, -360]])
        expected = np.tile([0.5, 0.2, 0], (3, 1))
        self.close(core.oklch_to_oklab(lch), expected)
        lab = [[0.2, -0.1, 0.3], [0.7, 0.15, -0.2]]
        self.close(core.oklch_to_oklab(core.oklab_to_oklch(lab)), lab)
        with self.assertRaises(ValueError):
            core.oklch_to_oklab([0.5, -0.1, 90])

    def test_invalid_numeric_values_are_rejected(self):
        functions = (core.srgb_to_linear, core.linear_to_srgb, core.linear_srgb_to_oklab,
                     core.oklab_to_linear_srgb, core.oklab_to_oklch, core.oklch_to_oklab)
        for fun in functions:
            for bad in ([True, False, True], ["0", "1", "0"], [0, complex(1, 1), 0],
                        [0, np.nan, 0], [0, np.inf, 0], [0, -np.inf, 0], [], [None] * 3):
                with self.subTest(function=fun.__name__, bad=repr(bad)), self.assertRaises(ValueError):
                    fun(bad)

    def test_wrong_triplet_shape_is_rejected(self):
        for fun in (core.linear_srgb_to_oklab, core.oklab_to_linear_srgb,
                    core.oklab_to_oklch, core.oklch_to_oklab):
            for bad in (0.5, [0, 1], np.ones((3, 2)), np.empty((0, 3))):
                with self.subTest(function=fun.__name__), self.assertRaises(ValueError):
                    fun(bad)

    def test_overflow_never_returns_infinity(self):
        for fun, values in ((core.srgb_to_linear, [1e308]),
                            (core.oklab_to_linear_srgb, [1e308, 1e308, 1e308])):
            with self.subTest(function=fun.__name__), self.assertRaises(ValueError):
                fun(values)

    def test_curve_hand_computed_values(self):
        # S_c(L) = L^c / (L^c + (1-L)^c); c=2 is an ANALYTIC TEST, not a look.
        self.close(core.lightness_curve([0, 0.25, 0.5, 0.75, 1], contrast=2),
                   [0, 0.1, 0.5, 0.9, 1])

    def test_plan_contrasts_monotonic_symmetric_fixed_endpoints(self):
        ramp = np.linspace(0, 1, 1001)
        for contrast in (1.25, 1.02, 0.82):
            curve = core.lightness_curve(ramp, contrast=contrast)
            self.assertEqual(curve[0], 0)
            self.assertEqual(curve[-1], 1)
            self.assertEqual(curve[500], 0.5)
            self.assertTrue(np.all(np.diff(curve) >= 0))
            self.close(curve + curve[::-1], np.ones_like(curve))
            if contrast > 1:
                self.assertLess(curve[250], ramp[250])
                self.assertGreater(curve[750], ramp[750])
            else:
                self.assertGreater(curve[250], ramp[250])

    def test_contrast_is_midpoint_slope(self):
        # Finite-difference step/tolerance are test instrumentation, not image parameters.
        h = 1e-6
        for contrast in (0.82, 1, 1.25, 2):
            values = core.lightness_curve([0.5-h, 0.5+h], contrast=contrast)
            self.assertAlmostEqual((values[1]-values[0])/(2*h), contrast, places=8)

    def test_curve_identity_and_strength_zero_are_exact_copies(self):
        lab = np.array([[0, 0, 0], [0.31, 0.14, -0.2], [1, 0, 0]])
        for contrast, strength in ((1.25, 0), (1, 0.6), (1, 1)):
            result = core.contrast_oklab(lab, contrast=contrast, strength=strength)
            np.testing.assert_array_equal(result, lab)
            self.assertFalse(np.shares_memory(result, lab))
        np.testing.assert_array_equal(core.lightness_curve(lab[:, 0], contrast=1), lab[:, 0])

    def test_contrast_only_changes_lightness_and_strength_interpolates(self):
        lab = np.array([[0.25, 0.1, -0.2], [0.75, -0.1, 0.2]])
        before = lab.copy()
        result = core.contrast_oklab(lab, contrast=2, strength=0.5)
        self.close(result[:, 0], [0.175, 0.825])
        np.testing.assert_array_equal(result[:, 1:], lab[:, 1:])
        np.testing.assert_array_equal(lab, before)
        # No gamut map is hidden here: non-displayable values survive for later QA.
        rgb = core.oklab_to_linear_srgb([[0.5, 1, 1]])
        self.assertTrue(np.any((rgb < 0) | (rgb > 1)))

    def test_curve_and_strength_invalid_parameters(self):
        for bad in (True, "1", 0, -1, np.nan, np.inf, [1]):
            with self.subTest(contrast=repr(bad)), self.assertRaises(ValueError):
                core.lightness_curve([0.5], contrast=bad)
        for bad in (True, "1", -0.01, 1.01, np.nan, np.inf, [1]):
            with self.subTest(strength=repr(bad)), self.assertRaises(ValueError):
                core.contrast_oklab([0.5, 0, 0], contrast=1.25, strength=bad)
        for bad in ([-0.1], [1.1], [np.nan]):
            with self.assertRaises(ValueError):
                core.lightness_curve(bad, contrast=1.25)
        with self.assertRaises(ValueError):
            core.contrast_oklab([1.1, 0, 0], contrast=1.25, strength=0)

    def test_full_color_path_rgb8_identity_without_intermediate_quantization(self):
        # Synthetic RGB8 lattice, not a photo. Quantize only in this test for comparison.
        axis = np.array([0, 1, 7, 32, 64, 128, 192, 254, 255], dtype=np.uint8)
        rgb8 = np.stack(np.meshgrid(axis, axis, axis, indexing="ij"), axis=-1)
        encoded = rgb8.astype(np.float64) / 255
        lab = core.linear_srgb_to_oklab(core.srgb_to_linear(encoded))
        unchanged = core.contrast_oklab(lab, contrast=1.25, strength=0)
        result = core.linear_to_srgb(core.oklab_to_linear_srgb(unchanged))
        self.close(result, encoded, atol=2e-13)
        np.testing.assert_array_equal(np.rint(result * 255).astype(np.uint8), rgb8)


if __name__ == "__main__":
    unittest.main(verbosity=2)
