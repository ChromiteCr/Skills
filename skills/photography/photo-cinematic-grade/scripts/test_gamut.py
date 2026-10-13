# SYNTHETIC numerical fixtures only. No photographs or confirmed look recipes.
# Origin: sRGB D65 Y fractions from W3C CSS Color 4 and exact line/cube algebra.
# Grids, seeds and test tolerances are instrumentation, not measured photo data.
from fractions import Fraction as F
import json
import unittest
import numpy as np
import color_core as core


class GamutTests(unittest.TestCase):
    def reference(self, row):
        # Independent EXACT rational reference; no module constants or helper use.
        v = [F(float(x)) for x in row]
        weights = [F(87098, 409605), F(175762, 245763), F(12673, 175545)]
        y = sum(w*x for w, x in zip(weights, v))
        if not 0 <= y <= 1:
            raise ValueError("unmappable luminance")
        factors = [F(1)]
        for x in v:
            if x < 0:
                factors.append(y/(y-x))
            if x > 1:
                factors.append((1-y)/(x-y))
        t = min(factors)
        return np.array([float(y+t*(x-y)) for x in v]), float(y), float(t)

    def mapped(self, source):
        return core.gamut_map_linear_srgb(source)

    def test_planned_mapping_api_exists(self):
        self.assertTrue(callable(getattr(core, "gamut_map_linear_srgb", None)))

    def test_in_gamut_lattice_is_exact_independent_copy(self):
        axis = np.linspace(0, 1, 9)
        source = np.stack(np.meshgrid(axis, axis, axis, indexing="ij"), axis=-1)
        out, qa = self.mapped(source)
        np.testing.assert_array_equal(out, source)
        self.assertFalse(np.shares_memory(out, source))
        self.assertEqual(qa["pixels_total"], 9**3)
        self.assertEqual(qa["pixels_mapped"], 0)
        self.assertEqual(qa["roundoff_samples_corrected"], 0)

    def test_negative_channels_match_exact_rational_reference(self):
        for row in ([-0.2, 0.4, 0.5], [0.4, -0.02, 0.5], [0.5, 0.4, -0.3]):
            with self.subTest(row=row):
                out, _ = self.mapped(row)
                np.testing.assert_allclose(out, self.reference(row)[0], rtol=0, atol=3e-15)
                self.assertLessEqual(out.min(), 3e-15)

    def test_above_white_channels_match_exact_rational_reference(self):
        for row in ([1.3, 0.4, 0.2], [0.1, 1.2, 0.2], [0.3, 0.4, 2]):
            out, _ = self.mapped(row)
            np.testing.assert_allclose(out, self.reference(row)[0], rtol=0, atol=3e-15)
            self.assertGreaterEqual(out.max(), 1-3e-15)

    def test_both_bounds_use_first_intersection_not_independent_clips(self):
        for row in ([-0.3, 0.4, 1.5], [1.4, 0.2, -0.1]):
            out, _ = self.mapped(row)
            np.testing.assert_allclose(out, self.reference(row)[0], rtol=0, atol=3e-15)
            self.assertFalse(np.array_equal(out, np.clip(row, 0, 1)))

    def test_luminance_and_ray_direction_on_synthetic_grid(self):
        rows = np.array([[r,g,b] for r in (-0.3, 0.2, 0.8, 1.3)
                         for g in (0.2, 0.5, 0.8) for b in (-0.3, 0.2, 0.8, 1.3)])
        weights = np.array([87098/409605, 175762/245763, 12673/175545])
        y = rows @ weights
        rows = rows[(y >= 0) & (y <= 1)]
        out, _ = self.mapped(rows)
        np.testing.assert_allclose(out @ weights, rows @ weights, rtol=0, atol=3e-15)
        for source, result in zip(rows, out):
            expected, _, _ = self.reference(source)
            np.testing.assert_allclose(result, expected, rtol=0, atol=3e-15)
        self.assertTrue(np.all((out >= 0) & (out <= 1)))

    def test_mapping_is_maximal_scale_on_the_selected_ray(self):
        source = np.array([-0.3, 0.4, 1.5])
        out, _ = self.mapped(source)
        expected, y, t = self.reference(source)
        np.testing.assert_allclose(out, expected, rtol=0, atol=3e-15)
        # Test-only perturbation above the exact first cube intersection.
        beyond = y + (t+1e-6)*(source-y)
        self.assertTrue(np.any((beyond < 0) | (beyond > 1)))

    def test_qa_counts_pixels_once_not_channels(self):
        source = np.array([[0,0,0], [1,1,1], [-0.3,0.4,1.5], [0.2,0.3,0.4]])
        _, qa = self.mapped(source)
        self.assertEqual(qa["pixels_total"], 4)
        self.assertEqual(qa["pixels_mapped"], 1)
        self.assertEqual(qa["mapped_fraction"], 0.25)
        self.assertEqual(qa["warning_fraction"], 0.1)
        self.assertEqual(qa["warnings"], ["gamut_mapped_fraction_above_10_percent"])
        self.assertNotIn("pass", qa)

    def test_warning_strictly_above_plan_ten_percent_boundary(self):
        source = np.full((10,3), 0.5)
        source[0] = [-0.2,0.4,0.5]
        _, qa = self.mapped(source)
        self.assertEqual(qa["mapped_fraction"], 0.1)
        self.assertEqual(qa["warnings"], [])
        source[1] = [1.3,0.4,0.2]
        self.assertTrue(self.mapped(source)[1]["warnings"])

    def test_json_report_discloses_algorithm_and_roundoff(self):
        _, qa = self.mapped([1.3,0.4,0.2])
        self.assertEqual(json.loads(json.dumps(qa, allow_nan=False)), qa)
        self.assertEqual(qa["algorithm"], "linear-srgb-luminance-ray-cube-v1")
        self.assertEqual(qa["input_space"], "linear-srgb-d65")
        self.assertEqual(qa["output_space"], "linear-srgb-d65")
        self.assertGreaterEqual(qa["roundoff_samples_corrected"], 0)
        self.assertGreaterEqual(qa["max_roundoff_correction"], 0)
        self.assertLessEqual(qa["max_roundoff_correction"], 3e-15)

    def test_unmappable_luminance_is_rejected_not_tone_mapped(self):
        for row in ([-0.1]*3, [1.1]*3, [-2,0.1,0.1], [1,2,1], [-1e308]*3, [1e308]*3):
            with self.subTest(row=row), self.assertRaisesRegex(ValueError, "luminance"):
                self.mapped(row)

    def test_invalid_types_shapes_and_nonfinite_rejected(self):
        for bad in (0.5, [], [0,1], np.empty((0,3)), [True]*3, ["0"]*3,
                    [None]*3, [0,1j,0], [0,np.nan,0], [0,np.inf,0], [[0,1,2],[0,1]]):
            with self.subTest(bad=repr(bad)), self.assertRaises(ValueError):
                self.mapped(bad)

    def test_shape_dtype_readonly_noncontiguous_no_mutation(self):
        for shape in ((3,), (4,3), (2,4,3)):
            source = np.broadcast_to(np.array([-0.2,0.4,0.5], dtype=np.float32), shape)
            before = source.copy()
            out, _ = self.mapped(source)
            self.assertEqual(out.shape, shape)
            self.assertEqual(out.dtype, np.float64)
            self.assertFalse(np.shares_memory(out, source))
            np.testing.assert_array_equal(source, before)
        source = np.tile([-0.2,0.4,0.5], (4,6,1))[:,::2]
        np.testing.assert_array_equal(self.mapped(source)[0], self.mapped(source.copy())[0])

    def test_repeatability_and_partition_count_accounting(self):
        source = np.array([[-0.3,0.4,1.5], [0,0,0], [1,1,1], [1.3,0.4,0.2]])
        out, qa = self.mapped(source)
        again, again_qa = self.mapped(source)
        self.assertEqual(out.tobytes(), again.tobytes())
        self.assertEqual(qa, again_qa)
        chunks = [self.mapped(row) for row in source]
        np.testing.assert_array_equal(out, np.stack([part[0] for part in chunks]))
        self.assertEqual(qa["pixels_mapped"], sum(part[1]["pixels_mapped"] for part in chunks))

    def test_one_ulp_excursions_count_as_mapped(self):
        source = [[np.nextafter(0.0,-1),0.5,0.5], [np.nextafter(1.0,2),0.5,0.5]]
        out, qa = self.mapped(source)
        self.assertEqual(qa["pixels_mapped"], 2)
        self.assertTrue(np.all((out >= 0) & (out <= 1)))

    def test_pipeline_oklab_to_mapping_encoding_and_quantization(self):
        # SYNTHETIC saturated Oklab probes, not approved six-look coefficients.
        lab = np.array([[0.5,0.3,0], [0.7,-0.3,0.2], [0.5,0,0]])
        linear = core.oklab_to_linear_srgb(lab)
        mapped, qa = self.mapped(linear)
        encoded = core.linear_to_srgb(mapped)
        rgb8 = core.quantize_srgb8(encoded, amplitude_lsb=0, seed=0)
        self.assertEqual(rgb8.dtype, np.uint8)
        self.assertGreater(qa["pixels_mapped"], 0)
        self.assertEqual(rgb8.tobytes(), core.quantize_srgb8(encoded, amplitude_lsb=0, seed=0).tobytes())

    def test_all_rgb8_codes_survive_zero_dither_identity_path(self):
        source = np.repeat(np.arange(256, dtype=np.uint8)[:,None], 3, axis=1)
        mapped, qa = self.mapped(core.srgb_to_linear(source.astype(float)/255))
        out = core.quantize_srgb8(core.linear_to_srgb(mapped), amplitude_lsb=0, seed=0)
        np.testing.assert_array_equal(out, source)
        self.assertEqual(qa["pixels_mapped"], 0)

    def test_neutral_endpoints_and_subnormal_in_gamut_are_unchanged(self):
        tiny = np.nextafter(0.0,1.0)
        source = np.array([[0,0,0], [1,1,1], [tiny]*3, [0.5]*3])
        out, qa = self.mapped(source)
        np.testing.assert_array_equal(out, source)
        self.assertEqual(qa["pixels_mapped"], 0)

    def test_mixed_batch_failure_preserves_source_and_publishes_no_partial_result(self):
        source = np.array([[-0.2,0.4,0.5], [2,2,2]])
        before = source.copy()
        with self.assertRaises(ValueError):
            self.mapped(source)
        np.testing.assert_array_equal(source, before)

    def test_is_idempotent_and_does_not_use_randomness(self):
        from unittest.mock import patch
        source = np.array([[-0.3,0.4,1.5], [1.3,0.4,0.2]])
        with patch.object(core.np.random, "Generator", side_effect=AssertionError("RNG forbidden")):
            once, _ = self.mapped(source)
            twice, qa = self.mapped(once)
        np.testing.assert_array_equal(twice, once)
        self.assertEqual(qa["pixels_mapped"], 0)


    def test_fortran_and_transposed_images_map_the_returned_array(self):
        # SYNTHETIC memory-layout regression; no photo or look parameters.
        base = np.tile([-0.2,0.4,0.5], (4,6,1))
        expected, _ = self.mapped(base)
        for source in (np.asfortranarray(base), base.transpose(1,0,2)):
            before = source.copy()
            out, qa = self.mapped(source)
            self.assertTrue(np.all((out >= 0) & (out <= 1)))
            target = expected if source.shape == base.shape else expected.transpose(1,0,2)
            np.testing.assert_array_equal(out, target)
            np.testing.assert_array_equal(source, before)
            self.assertFalse(np.shares_memory(out, source))
            self.assertEqual(qa["pixels_mapped"], 24)



if __name__ == "__main__":
    unittest.main(verbosity=2)
