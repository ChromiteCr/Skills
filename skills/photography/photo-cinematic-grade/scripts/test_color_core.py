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




class HighlightRolloffTests(unittest.TestCase):
    # SYNTHETIC mathematical fixtures, not photographs or approved look recipes.
    # start=0.5, strengths, chroma values, ramps and tolerances are test choices.
    # The polynomial is derived from endpoint/slope constraints, not prototype data.
    # No default shoulder onset or visual acceptance has been confirmed by Bill.
    def roll(self, lab, start=0.5, strength=1):
        return core.highlight_rolloff_oklab(lab, start=start, strength=strength)

    def test_hand_computed_shoulder(self):
        lab = np.array([[x, 0.25, -0.5] for x in (0, 0.5, 0.625, 0.75, 0.875, 1)])
        expected = lab.copy()
        expected[:, 1:] *= np.array([1, 1, 27/32, 1/2, 5/32, 0])[:, None]
        np.testing.assert_array_equal(self.roll(lab), expected)

    def test_strength_interpolates_chroma_not_lightness(self):
        lab = np.array([[0.75, 0.25, -0.5], [1, 0.25, -0.5]])
        expected = [[0.75, 0.21875, -0.4375], [1, 0.1875, -0.375]]
        np.testing.assert_array_equal(self.roll(lab, strength=0.25), expected)

    def test_at_and_below_start_are_exact(self):
        lab = np.array([[0, 1e308, -1e308], [0.25, 0.12, -0.34], [0.5, -0.1, 0.2]])
        out = self.roll(lab)
        np.testing.assert_array_equal(out, lab)
        self.assertFalse(np.shares_memory(out, lab))

    def test_zero_strength_exact_independent_copy(self):
        lab = np.array([[0.75, 1, -1], [1, 0.25, -0.5]])
        out = self.roll(lab, strength=0)
        np.testing.assert_array_equal(out, lab)
        self.assertFalse(np.shares_memory(out, lab))

    def test_preserves_lightness_and_neutral_axis(self):
        lab = np.zeros((1001, 3))
        lab[:, 0] = np.linspace(0, 1, 1001)
        np.testing.assert_array_equal(self.roll(lab), lab)
        lab[:, 1:] = [0.25, -0.5]
        np.testing.assert_array_equal(self.roll(lab)[:, 0], lab[:, 0])

    def test_hue_preserved_until_zero_chroma(self):
        lch = np.array([[0.75, 0.2, h] for h in range(0, 360, 15)])
        after = core.oklab_to_oklch(self.roll(core.oklch_to_oklab(lch)))
        np.testing.assert_allclose(after[:, 1], 0.1, rtol=0, atol=1e-15)
        np.testing.assert_allclose(after[:, 2], lch[:, 2], rtol=0, atol=1e-12)
        white = core.oklab_to_oklch(self.roll([1, 0.2, -0.1]))
        np.testing.assert_array_equal(white, [1, 0, 0])

    def test_monotone_bounded_chroma_for_ramps(self):
        lab = np.array([[x, 1, 0] for x in np.linspace(0, 1, 1001)])
        for start in (0, 0.5, 0.9):
            for strength in (0, 0.25, 1):
                out = self.roll(lab, start, strength)
                self.assertTrue(np.all(np.diff(out[:, 1]) <= 0))
                self.assertTrue(np.all((out[:, 1] >= 1-strength) & (out[:, 1] <= 1)))
                self.assertEqual(out[0, 1], 1)
                self.assertEqual(out[-1, 1], 1-strength)

    def test_zero_endpoint_slopes_and_join_continuity(self):
        # One-sided finite differences. 1e-5 and 2e-4 are test instrumentation.
        h = 1e-5
        out = self.roll([[0.5-h, 1, 0], [0.5, 1, 0], [0.5+h, 1, 0],
                         [1-h, 1, 0], [1, 1, 0]])[:, 1]
        self.assertEqual(out[0], out[1])
        self.assertLess(abs((out[2]-out[1])/h), 2e-4)
        self.assertLess(abs((out[4]-out[3])/h), 2e-4)

    def test_triplet_image_and_readonly_noncontiguous_input(self):
        for shape in ((3,), (4, 3), (2, 4, 3)):
            lab = np.full(shape, 0.75, dtype=np.float32)
            before = lab.copy()
            lab.setflags(write=False)
            out = self.roll(lab)
            self.assertEqual(out.shape, shape)
            self.assertEqual(out.dtype, np.float64)
            np.testing.assert_array_equal(lab, before)
            self.assertFalse(np.shares_memory(out, lab))
        lab = np.full((4, 6, 3), 0.75)[:, ::2]
        before = lab.copy()
        self.roll(lab)
        np.testing.assert_array_equal(lab, before)

    def test_rejects_invalid_coordinates(self):
        for bad in (0.5, [0, 1], [], np.empty((0, 3)), [True]*3, ["0.5"]*3,
                    [None]*3, [0.5, 1j, 0], [np.nan, 0, 0], [0.5, np.inf, 0],
                    [-0.01, 0, 0], [1.01, 0, 0]):
            with self.subTest(bad=repr(bad)), self.assertRaises(ValueError):
                self.roll(bad)

    def test_rejects_invalid_start_and_strength_even_when_disabled(self):
        for bad in (True, "0.5", [0.5], -0.01, 1, 1.01, np.nan, np.inf):
            with self.subTest(start=repr(bad)), self.assertRaises(ValueError):
                self.roll([0.75, 0.1, 0.2], start=bad, strength=0)
        for bad in (True, "0.5", [0.5], -0.01, 1.01, np.nan, np.inf):
            with self.subTest(strength=repr(bad)), self.assertRaises(ValueError):
                self.roll([0.75, 0.1, 0.2], strength=bad)
        with self.assertRaises(ValueError):
            self.roll([1.01, 0, 0], strength=0)

    def test_no_implicit_recipe_parameters(self):
        with self.assertRaises(TypeError):
            core.highlight_rolloff_oklab([0.75, 0.1, 0.2])
        with self.assertRaises(TypeError):
            core.highlight_rolloff_oklab([0.75, 0.1, 0.2], start=0.5)
        with self.assertRaises(TypeError):
            core.highlight_rolloff_oklab([0.75, 0.1, 0.2], strength=1)

    def test_extreme_legal_start_and_large_chroma_stay_finite(self):
        start = np.nextafter(1.0, 0.0)
        lab = [[start, 1e308, -1e308], [1, 1e308, -1e308]]
        out = self.roll(lab, start=start)
        self.assertTrue(np.all(np.isfinite(out)))
        np.testing.assert_array_equal(out, [[start, 1e308, -1e308], [1, 0, 0]])

    def test_near_white_residual_does_not_cancel_to_zero(self):
        # At start=0, epsilon=2^-53. f(1-epsilon)=3*epsilon^2-2*epsilon^3.
        lightness = np.nextafter(1.0, 0.0)
        out = self.roll([lightness, 1, 0], start=0)
        self.assertGreater(out[1], 0)
        self.assertAlmostEqual(out[1] / (3 * 2.0**-106), 1, places=14)

    def test_no_hidden_gamut_clipping_or_quantization(self):
        out = self.roll([0.75, 1, -1])
        np.testing.assert_array_equal(out, [0.75, 0.5, -0.5])
        rgb = core.oklab_to_linear_srgb(out)
        self.assertTrue(np.any((rgb < 0) | (rgb > 1)))
        subtle = self.roll([0.75, 1e-6, 0])
        self.assertEqual(subtle[1], 0.5e-6)

    def test_color_core_pipeline_repeated_and_disabled_identity(self):
        # Synthetic RGB lattice. No CLI replacement, output file or photo acceptance.
        axis = np.array([0, 1, 32, 128, 254, 255], dtype=np.float64) / 255
        encoded = np.stack(np.meshgrid(axis, axis, axis, indexing="ij"), axis=-1)
        lab = core.linear_srgb_to_oklab(core.srgb_to_linear(encoded))
        toned = core.contrast_oklab(lab, contrast=1.25, strength=1)
        rolled = self.roll(toned)
        np.testing.assert_array_equal(self.roll(toned), rolled)
        self.assertTrue(np.any(rolled[..., 1:] != toned[..., 1:]))
        np.testing.assert_array_equal(rolled[..., 0], toned[..., 0])
        disabled = self.roll(core.contrast_oklab(lab, contrast=1.25, strength=0), strength=0)
        after = core.linear_to_srgb(core.oklab_to_linear_srgb(disabled))
        np.testing.assert_allclose(after, encoded, rtol=0, atol=2e-13)


if __name__ == "__main__":
    unittest.main(verbosity=2)
