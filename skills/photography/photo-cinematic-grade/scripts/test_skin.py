# SYNTHETIC mathematical fixtures, not photographs or confirmed look recipes.
# Origin: constructed OkLCh vectors, circular-angle geometry and plan 3.5 limits.
# Values, sample sizes and tolerances are test instrumentation only.
import json
import math
import unittest
from unittest.mock import patch
import numpy as np
import color_core as core


class SkinProtectionTests(unittest.TestCase):
    def protect(self, source, graded, mask):
        return core.protect_skin_oklch(source, graded, mask)

    def test_planned_protection_api_exists(self):
        self.assertTrue(callable(getattr(core, "protect_skin_oklch", None)))

    def test_hand_calculated_hue_and_chroma_limits(self):
        source = [[0.6, 0.1, 60], [0.5, 0.2, 60]]
        graded = [[0.7, 0.3, 100], [0.4, 0.3, 20]]
        out, qa = self.protect(source, graded, [True, True])
        np.testing.assert_allclose(out, [[0.7, 0.115, 66], [0.4, 0.23, 54]], rtol=0, atol=1e-15)
        self.assertEqual(qa["hue_limited_pixels"], 2)
        self.assertEqual(qa["chroma_limited_pixels"], 2)
        self.assertEqual(qa["changed_pixels"], 2)

    def test_unselected_pixels_and_all_lightness_remain_exact(self):
        source = np.array([[0.6, 0.1, 60], [0.5, 0.2, 60]])
        graded = np.array([[0.7, 0.3, 100], [0.4, 0.3, 20]])
        out, qa = self.protect(source, graded, [True, False])
        np.testing.assert_array_equal(out[1], graded[1])
        np.testing.assert_array_equal(out[:, 0], graded[:, 0])
        self.assertEqual(qa["selected_pixels"], 1)

    def test_small_changes_keep_exact_noncanonical_hue(self):
        source = [[0.5, 0.1, -2], [0.5, 0.2, 65]]
        graded = np.array([[0.6, 0.1, 721], [0.6, 0.1, -299]])
        out, qa = self.protect(source, graded, [True, True])
        np.testing.assert_array_equal(out, graded)
        self.assertEqual(qa["changed_pixels"], 0)

    def test_wrap_seam_and_both_rotation_directions(self):
        source = [[0.5, 0.1, 359], [0.5, 0.1, 1], [0.5, 0.1, -179]]
        graded = [[0.5, 0.1, 20], [0.5, 0.1, 340], [0.5, 0.1, 179]]
        out, _ = self.protect(source, graded, [True]*3)
        np.testing.assert_array_equal(out[:, 2], [5, 355, 179])

    def test_exact_limit_boundary_is_not_a_change(self):
        source = [[0.5, 1.0, 60], [0.5, 1.0, 60]]
        graded = np.array([[0.5, 1.15, 66], [0.5, 1.15, 54]])
        out, qa = self.protect(source, graded, [True]*2)
        np.testing.assert_array_equal(out, graded)
        self.assertEqual(qa["changed_pixels"], 0)

    def test_opposite_hues_have_documented_positive_tie(self):
        out, _ = self.protect([[0.5, 0.1, 0], [0.5, 0.1, 180]],
                              [[0.5, 0.1, 180], [0.5, 0.1, 0]], [True]*2)
        np.testing.assert_array_equal(out[:, 2], [6, 186])

    def test_zero_source_chroma_removes_tint_without_inventing_hue(self):
        out, qa = self.protect([0.5, 0, 17], [0.7, 0.2, 111], True)
        np.testing.assert_array_equal(out, [0.7, 0, 111])
        self.assertEqual(qa["source_achromatic_pixels"], 1)
        self.assertEqual(qa["hue_limited_pixels"], 0)

    def test_desaturation_is_preserved_and_zero_target_hue_is_undefined(self):
        graded = np.array([[0.7, 0, 222], [0.7, 0.01, 63]])
        out, qa = self.protect([[0.5, 0.1, 60]]*2, graded, [True]*2)
        np.testing.assert_array_equal(out, graded)
        self.assertEqual(qa["hue_comparable_pixels"], 1)

    def test_no_selection_is_explicitly_unavailable_not_a_pass(self):
        out, qa = self.protect([0.5, 0.1, 60], [0.7, 0.3, 120], False)
        np.testing.assert_array_equal(out, [0.7, 0.3, 120])
        self.assertEqual(qa["warnings"], ["no_skin_pixels_selected"])
        self.assertNotIn("pass", qa)

    def test_mask_requires_boolean_dtype_and_exact_shape(self):
        for mask in (1, 0.5, "skin", None, [True], [1, 0], [[True, False]], True):
            with self.subTest(mask=repr(mask)), self.assertRaises(ValueError):
                self.protect([[0.5, 0.1, 60]]*2, [[0.6, 0.2, 100]]*2, mask)

    def test_both_coordinate_arrays_validate_even_when_mask_is_false(self):
        bad_values = (0.5, [], [0, 1], [True]*3, ["0"]*3, [0, 1j, 0],
                      [0.5, -0.1, 60], [-0.1, 0.1, 60], [1.1, 0.1, 60],
                      [0.5, np.nan, 60], [0.5, 0.1, np.inf])
        good = [0.5, 0.1, 60]
        for bad in bad_values:
            for source, graded in ((bad, good), (good, bad)):
                with self.subTest(bad=repr(bad)), self.assertRaises(ValueError):
                    self.protect(source, graded, False)
        with self.assertRaises(ValueError):
            self.protect(good, [good, good], [True, True])

    def test_readonly_float32_and_noncontiguous_inputs_are_not_mutated(self):
        base = np.tile(np.array([0.5, 0.1, 60], dtype=np.float32), (4, 6, 1))
        graded_base = np.tile([0.7, 0.3, 100], (4, 6, 1))
        for source, graded in ((base[:, ::2], graded_base[:, ::2]),
                               (np.asfortranarray(base), np.asfortranarray(graded_base)),
                               (base.transpose(1, 0, 2), graded_base.transpose(1, 0, 2))):
            source.setflags(write=False)
            graded.setflags(write=False)
            source_copy, graded_copy = source.copy(), graded.copy()
            out, _ = self.protect(source, graded, np.ones(source.shape[:-1], dtype=bool))
            self.assertEqual(out.dtype, np.float64)
            self.assertEqual(out.shape, source.shape)
            self.assertFalse(np.shares_memory(out, source))
            self.assertFalse(np.shares_memory(out, graded))
            np.testing.assert_allclose(out[..., 1], source[..., 1].astype(float)*1.15, rtol=0, atol=0)
            np.testing.assert_array_equal(source, source_copy)
            np.testing.assert_array_equal(graded, graded_copy)

    def test_all_code_path_identities_have_independent_outputs(self):
        source = np.array([[0.5, 0.1, 60], [0, 0, 0], [1, 0, 0]])
        out, qa = self.protect(source, source, [True]*3)
        np.testing.assert_array_equal(out, source)
        self.assertFalse(np.shares_memory(out, source))
        self.assertEqual(qa["changed_pixels"], 0)

    def test_report_is_json_and_stage_scoped_with_plan_limits(self):
        _, qa = self.protect([0.5, 0.1, 60], [0.7, 0.3, 100], True)
        self.assertEqual(json.loads(json.dumps(qa, allow_nan=False)), qa)
        self.assertEqual(qa["algorithm"], "oklch-explicit-skin-limits-v1")
        self.assertEqual(qa["scope"], "explicit_mask_before_gamut_and_quantization")
        self.assertEqual(qa["hue_limit_degrees"], 6)
        self.assertEqual(qa["chroma_ratio_limit"], 1.15)
        self.assertEqual(qa["pixels_total"], 1)
        self.assertFalse(qa["skin_detection_performed"])
        self.assertNotIn("pass", qa)

    def test_repeatability_idempotence_and_no_randomness(self):
        with patch.object(core.np.random, "Generator", side_effect=AssertionError("RNG forbidden")):
            source, graded = [0.5, 0.1, 359], [0.7, 0.3, 100]
            out, qa = self.protect(source, graded, True)
            again, again_qa = self.protect(source, graded, True)
            twice, twice_qa = self.protect(source, out, True)
        self.assertEqual(out.tobytes(), again.tobytes())
        self.assertEqual(qa, again_qa)
        np.testing.assert_array_equal(twice, out)
        self.assertEqual(twice_qa["changed_pixels"], 0)

    def test_hue_grid_matches_independent_trigonometric_reference(self):
        source_hue = np.arange(0, 360, 11, dtype=float)
        target_hue = np.mod(source_hue*7+23, 360)
        source = np.column_stack([np.full(len(source_hue), 0.5), np.full(len(source_hue), 0.1), source_hue])
        graded = np.column_stack([np.full(len(source_hue), 0.6), np.full(len(source_hue), 0.2), target_hue])
        out, _ = self.protect(source, graded, np.ones(len(source_hue), dtype=bool))
        for before, after, result in zip(source_hue, target_hue, out[:, 2]):
            angle = math.radians(after-before)
            delta = math.degrees(math.atan2(math.sin(angle), math.cos(angle)))
            expected = (before+max(-6, min(6, delta))) % 360
            circular_error = (result-expected+180) % 360-180
            self.assertLessEqual(abs(circular_error), 1e-12)

    def test_huge_finite_chroma_and_hue_do_not_overflow(self):
        huge = np.finfo(float).max
        for chroma in (huge, huge/2):
            with np.errstate(all="raise"):
                out, _ = self.protect([0.5, chroma, huge], [0.7, huge, -huge], True)
            self.assertTrue(np.isfinite(out).all())
            self.assertLessEqual(out[1], huge)
            self.assertEqual(out[0], 0.7)

    def test_subnormal_chroma_uses_no_guessed_neutral_cutoff(self):
        tiny = np.nextafter(0.0, 1.0)
        out, qa = self.protect([0.5, tiny, 60], [0.7, tiny*4, 100], True)
        self.assertEqual(out[1], tiny)
        self.assertEqual(out[2], 66)
        self.assertEqual(qa["source_achromatic_pixels"], 0)

    def test_pipeline_split_toning_protection_gamut_and_quantization(self):
        # SYNTHETIC warm color patch, not measured human skin or approved recipe.
        source = np.array([[0.6, 0.05, 60], [0.4, 0.08, 220]])
        lab = core.oklch_to_oklab(source)
        graded = core.oklab_to_oklch(core.split_tone_oklab(lab, shadow_hue=238,
            shadow_chroma=0.1, highlight_hue=345, highlight_chroma=0.1, balance=0.5, strength=1))
        protected, qa = self.protect(source, graded, [True, False])
        self.assertGreater(qa["changed_pixels"], 0)
        np.testing.assert_array_equal(protected[1], graded[1])
        linear, _ = core.gamut_map_linear_srgb(core.oklab_to_linear_srgb(core.oklch_to_oklab(protected)))
        out = core.quantize_srgb8(core.linear_to_srgb(linear), amplitude_lsb=0, seed=0)
        self.assertEqual(out.shape, (2, 3))
        self.assertEqual(out.dtype, np.uint8)
        # Downstream gamut/quantization still require final-image skin QA.

    def test_changed_counts_are_union_not_sum_and_partition_consistent(self):
        source = np.array([[0.5, 0.1, 60]]*4)
        graded = np.array([[0.6, 0.3, 100], [0.6, 0.1, 100], [0.6, 0.3, 60], [0.6, 0.1, 60]])
        out, qa = self.protect(source, graded, [True]*4)
        self.assertEqual(qa["changed_pixels"], 3)
        self.assertEqual(qa["hue_limited_pixels"], 2)
        self.assertEqual(qa["chroma_limited_pixels"], 2)
        chunks = [self.protect(s, g, True) for s, g in zip(source, graded)]
        np.testing.assert_array_equal(out, np.stack([item[0] for item in chunks]))
        self.assertEqual(qa["changed_pixels"], sum(item[1]["changed_pixels"] for item in chunks))


if __name__ == "__main__":
    unittest.main(verbosity=2)
