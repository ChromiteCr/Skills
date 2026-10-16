"""SYNTHETIC tests, not photographs or approved creative recipes.

Pixels and constant +/-16 channel offsets below are constructed solely for
exact clamp-count and threshold tests. The offsets use the existing recipe
schema bounds; they are NOT proposed or user-confirmed photographic settings.
The 10% warning boundary comes from AUDIT-AND-IDEAS.md section 3.5.
"""
from contextlib import redirect_stdout
import copy
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

from PIL import Image, ImageCms

import cinegrade as c
from image_io import InputError

HERE = Path(__file__).resolve().parent
WARNING = "encoded_srgb_clamped_fraction_above_10_percent"


class CliGamutQATests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix=".synthetic-gamut-qa-", dir=HERE)
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.looks = copy.deepcopy(c.load_looks())
        neutral = copy.deepcopy(self.looks["neutral"])
        for name in ("warm-muted", "cool-muted"):
            self.looks[name] = copy.deepcopy(neutral)
            # SYNTHETIC stress recipe; not a photographic recommendation.
            self.looks[name]["shadow_rgb"] = [16, 16, 16]
            self.looks[name]["highlight_rgb"] = [16, 16, 16]
        self.recipe = self.looks["warm-muted"]

    def image(self, pixels):
        image = Image.new("RGB", (len(pixels), 1))
        image.putdata(pixels)
        return image

    def source(self, image):
        path = self.root / "synthetic.png"
        profile = ImageCms.ImageCmsProfile(ImageCms.createProfile("sRGB")).tobytes()
        image.save(path, icc_profile=profile)
        return path

    def report(self, command, image, **kwargs):
        source = self.source(image)
        target = self.root / command
        with mock.patch.object(c, "load_looks", return_value=self.looks):
            result = getattr(c, command)(source, target, **kwargs)
        persisted = json.loads((target / "report.json").read_text())
        self.assertEqual(persisted, result)
        return result

    def test_counts_pixels_once_when_multiple_channels_clamp(self):
        image = self.image([(255, 255, 255), (255, 128, 0), (0, 0, 0), (120, 120, 120)])
        result, channels, qa = c.grade_pixels_with_qa(image, self.recipe, 100)
        self.assertEqual(list(result.getdata()), [(255, 255, 255), (255, 144, 16), (16, 16, 16), (136, 136, 136)])
        self.assertEqual(channels, 4)
        self.assertEqual((qa["pixels_total"], qa["pixels_mapped"], qa["mapped_fraction"]), (4, 2, 0.5))

    def test_negative_excursions_count_the_pixel_union(self):
        recipe = copy.deepcopy(self.recipe)
        recipe["shadow_rgb"] = recipe["highlight_rgb"] = [-16, -16, -16]
        image = self.image([(0, 0, 0), (0, 128, 255), (120, 120, 120)])
        result, channels, qa = c.grade_pixels_with_qa(image, recipe, 100)
        self.assertEqual(list(result.getdata()), [(0, 0, 0), (0, 112, 239), (104, 104, 104)])
        self.assertEqual(channels, 4)
        self.assertEqual(qa["pixels_mapped"], 2)

    def test_neutral_endpoints_are_not_clipping_evidence(self):
        image = self.image([(0, 0, 0), (255, 255, 255)])
        result, channels, qa = c.grade_pixels_with_qa(image, self.looks["neutral"], 100)
        self.assertEqual(result.tobytes(), image.tobytes())
        self.assertEqual(channels, 0)
        self.assertEqual(qa["mapped_fraction"], 0)
        self.assertEqual(qa["warnings"], [])

    def test_exact_ten_percent_does_not_warn(self):
        image = self.image([(255, 255, 255)] + [(120, 120, 120)] * 9)
        _, channels, qa = c.grade_pixels_with_qa(image, self.recipe, 100)
        self.assertEqual(channels, 3)
        self.assertEqual(qa["mapped_fraction"], 0.1)
        self.assertEqual(qa["warnings"], [])

    def test_above_ten_percent_warns(self):
        image = self.image([(255, 255, 255)] + [(120, 120, 120)] * 8)
        _, _, qa = c.grade_pixels_with_qa(image, self.recipe, 100)
        self.assertEqual(qa["mapped_fraction"], 1 / 9)
        self.assertEqual(qa["warnings"], [WARNING])

    def test_below_ten_percent_does_not_warn(self):
        image = self.image([(255, 255, 255)] + [(120, 120, 120)] * 10)
        _, _, qa = c.grade_pixels_with_qa(image, self.recipe, 100)
        self.assertEqual(qa["mapped_fraction"], 1 / 11)
        self.assertEqual(qa["warnings"], [])

    def test_zero_strength_bypasses_mapping_and_returns_independent_pixels(self):
        image = self.image([(255, 255, 255), (0, 0, 0)])
        result, channels, qa = c.grade_pixels_with_qa(image, self.recipe, 0)
        self.assertIsNot(result, image)
        self.assertEqual(result.tobytes(), image.tobytes())
        self.assertEqual(channels, 0)
        self.assertFalse(qa["applied"])
        self.assertEqual((qa["pixels_total"], qa["pixels_mapped"]), (2, 0))
        self.assertEqual(qa["warnings"], [])

    def test_full_strength_stage_count_is_not_changed_output_count(self):
        image = self.image([(255, 255, 255)])
        for strength in (1, 60, 100):
            with self.subTest(strength=strength):
                result, channels, qa = c.grade_pixels_with_qa(image, self.recipe, strength)
                self.assertEqual(result.tobytes(), image.tobytes())
                self.assertEqual(channels, 3)
                self.assertEqual(qa["pixels_mapped"], 1)
                self.assertEqual(qa["scope"], "full_strength_before_strength_mix")

    def test_changed_pixels_can_have_zero_mapping(self):
        image = self.image([(120, 120, 120)])
        result, channels, qa = c.grade_pixels_with_qa(image, self.recipe, 100)
        self.assertEqual(list(result.getdata()), [(136, 136, 136)])
        self.assertEqual(channels, 0)
        self.assertEqual(qa["pixels_mapped"], 0)

    def test_existing_two_result_api_and_input_are_preserved(self):
        image = self.image([(0, 0, 0), (128, 128, 128), (255, 255, 255)])
        before = image.tobytes()
        recipe_before = copy.deepcopy(self.recipe)
        legacy, channels = c.grade_pixels(image, self.recipe, 50)
        result, count, qa = c.grade_pixels_with_qa(image, self.recipe, 50)
        self.assertEqual(list(legacy.getdata()), [(8, 8, 8), (136, 136, 136), (255, 255, 255)])
        self.assertEqual(legacy.tobytes(), result.tobytes())
        self.assertEqual(channels, count)
        self.assertEqual(image.tobytes(), before)
        self.assertEqual(self.recipe, recipe_before)
        self.assertEqual(qa, c.grade_pixels_with_qa(image, self.recipe, 50)[2])

    def test_empty_images_rejected_without_inventing_a_fraction(self):
        with self.assertRaises(InputError):
            c.grade_pixels_with_qa(Image.new("RGB", (0, 1)), self.recipe, 100)

    def test_invalid_mode_and_strength_keep_input_contract(self):
        image = self.image([(128, 128, 128)])
        for strength in (-1, 101, True, 0.5, "60"):
            with self.subTest(strength=strength), self.assertRaises(InputError):
                c.grade_pixels_with_qa(image, self.recipe, strength)
        with self.assertRaises(InputError):
            c.grade_pixels_with_qa(image.convert("RGBA"), self.recipe, 100)

    def test_render_persists_full_resolution_pixel_fraction(self):
        image = self.image([(255, 255, 255)] + [(120, 120, 120)] * 8)
        report = self.report("render", image, strength=50)
        qa = report["qa"]["gamut_mapping"]
        self.assertEqual((qa["pixels_total"], qa["pixels_mapped"]), (9, 1))
        self.assertEqual(qa["mapped_fraction"], 1 / 9)
        self.assertEqual(qa["warnings"], [WARNING])
        self.assertEqual(report["qa"]["full_strength_pre_clamp_channel_samples"], 3)
        self.assertEqual(report["qa"]["warnings"], ["grade_out_of_range_before_clamp"])

    def test_compare_counts_only_after_panel_and_matches_render(self):
        image = self.image([(255, 255, 255), (120, 120, 120)])
        render = self.report("render", image, strength=60)
        report = self.report("compare", image, look="warm-muted", strength=60)
        self.assertEqual(report["output"]["dimensions"], [4, 1])
        self.assertEqual(report["qa"]["gamut_mapping"]["pixels_total"], 2)
        self.assertEqual(report["qa"]["gamut_mapping"], render["qa"]["gamut_mapping"])

    def test_candidates_measure_actual_resized_preview_and_neutral_bypass(self):
        report = self.report("candidates", Image.new("RGB", (4, 2), "white"), strength=60, max_edge=2)
        self.assertEqual(report["preview"]["dimensions"], [2, 1])
        self.assertEqual(report["qa"]["scope"], "resized_preview_only")
        for item in report["candidates"]:
            qa = item["qa"]["gamut_mapping"]
            neutral = item["grade"]["look"] == "neutral"
            self.assertEqual(qa["pixels_total"], 2)
            self.assertEqual(qa["pixels_mapped"], 0 if neutral else 2)
            self.assertEqual(qa["warnings"], [] if neutral else [WARNING])

    def test_cli_surfaces_stage_warning_for_all_three_commands(self):
        source = self.source(self.image([(255, 255, 255)]))
        for command in ("render", "candidates", "compare"):
            with self.subTest(command=command):
                args = [command, str(source), "--output", str(self.root / command), "--strength", "60"]
                if command == "compare":
                    args += ["--look", "warm-muted"]
                output = io.StringIO()
                with mock.patch.object(c, "load_looks", return_value=self.looks), redirect_stdout(output):
                    code = c.main(args)
                self.assertEqual(code, 0)
                warnings = json.loads(output.getvalue())["warnings"]
                self.assertIn("grade_out_of_range_before_clamp", warnings)
                self.assertEqual(warnings.count(WARNING), 1)
                self.assertNotIn(str(self.root), output.getvalue())

    def test_stage_metadata_discloses_legacy_algorithm_and_exclusions(self):
        _, _, qa = c.grade_pixels_with_qa(self.image([(255, 255, 255)]), self.recipe, 100)
        self.assertEqual(qa["algorithm"], "encoded-srgb-channel-clamp-v1")
        self.assertEqual(qa["warning_threshold_fraction"], 0.1)
        self.assertIn("excludes_source_icc_conversion", qa["limitations"])
        self.assertIn("not_linear_srgb_mapping", qa["limitations"])
        self.assertIn("not_final_output_clipping_or_visual_acceptance", qa["limitations"])
        self.assertNotIn("pass", qa)
        self.assertEqual(json.loads(json.dumps(qa, allow_nan=False)), qa)

    def test_real_cli_subprocess_with_bundled_recipe_and_synthetic_pixels(self):
        source = self.source(self.image([(0, 0, 0), (255, 255, 255)]))
        target = self.root / "cli-default"
        proc = subprocess.run([sys.executable, "-B", str(HERE / "cinegrade.py"), "render", str(source),
                               "--output", str(target), "--look", "neutral", "--strength", "100"],
                              capture_output=True, text=True, timeout=20)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(json.loads(proc.stdout)["warnings"], [])
        qa = json.loads((target / "report.json").read_text())["qa"]["gamut_mapping"]
        self.assertEqual(qa["pixels_total"], 2)
        self.assertEqual(qa["mapped_fraction"], 0)


if __name__ == "__main__":
    unittest.main()
