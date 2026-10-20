# SYNTHETIC mathematical/software fixtures only, constructed in this module.
# Colors, sizes and metadata probe counting, boundaries and privacy; they are
# not photographs, observed scene data or photographer-confirmed settings.
import colorsys
import hashlib
import itertools
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

from PIL import Image, ImageCms, PngImagePlugin

import photo_analysis
from image_io import InputError, LoadedImage

HERE = Path(__file__).resolve().parent


def rgb(pixels):
    image = Image.new("RGB", (len(pixels), 1))
    image.putdata(pixels)
    return image


class AnalysisTests(unittest.TestCase):
    def test_primary_secondary_boundary_counts(self):
        # HSV 0, 60, 120, 180, 240, 300 degrees, then undefined-hue grays.
        pixels = [(255, 0, 0), (255, 255, 0), (0, 255, 0),
                  (0, 255, 255), (0, 0, 255), (255, 0, 255),
                  (0, 0, 0), (128, 128, 128), (255, 255, 255)]
        result = photo_analysis.measure_pixels(rgb(pixels))
        hue = result["hue_families"]
        self.assertEqual(hue["achromatic_pixels"], 3)
        self.assertEqual(hue["chromatic_pixels"], 6)
        self.assertEqual([s["pixels"] for s in hue["sectors"]], [1] * 6)
        self.assertEqual([s["fraction_of_all_pixels"] for s in hue["sectors"]], [1 / 9] * 6)
        self.assertEqual([s["fraction_of_chromatic_pixels"] for s in hue["sectors"]], [1 / 6] * 6)
        self.assertAlmostEqual(result["saturation"]["mean_all_pixels"], 2 / 3)

    def test_each_boundary_and_both_neighbors(self):
        # Explicitly enumerated RGB hexagon neighbors, including hue wrap.
        groups = [([(255, 0, 1), (255, 0, 0), (255, 1, 0)], [5, 0, 0]),
                  ([(255, 254, 0), (255, 255, 0), (254, 255, 0)], [0, 1, 1]),
                  ([(1, 255, 0), (0, 255, 0), (0, 255, 1)], [1, 2, 2]),
                  ([(0, 255, 254), (0, 255, 255), (0, 254, 255)], [2, 3, 3]),
                  ([(0, 1, 255), (0, 0, 255), (1, 0, 255)], [3, 4, 4]),
                  ([(254, 0, 255), (255, 0, 255), (255, 0, 254)], [4, 5, 5])]
        for pixels, sectors in groups:
            for pixel, sector in zip(pixels, sectors):
                with self.subTest(pixel=pixel):
                    values = photo_analysis.measure_pixels(rgb([pixel]))["hue_families"]["sectors"]
                    self.assertEqual([s["pixels"] for s in values], [int(i == sector) for i in range(6)])

    def test_scalar_colorsys_oracle_on_synthetic_lattice(self):
        # Independent standard-library conversion. Exact ties are covered by
        # explicit assertions above, avoiding floating oracle edge ambiguity.
        pixels = list(itertools.product((0, 1, 63, 127, 128, 254, 255), repeat=3))
        expected = [0] * 6
        saturation = []
        for pixel in pixels:
            h, s, _ = colorsys.rgb_to_hsv(*(value / 255 for value in pixel))
            saturation.append(s)
            if s:
                position = h * 6
                if abs(position - round(position)) < 1e-12:
                    position = round(position)
                expected[int(position) % 6] += 1
        result = photo_analysis.measure_pixels(rgb(pixels))
        self.assertEqual([s["pixels"] for s in result["hue_families"]["sectors"]], expected)
        self.assertAlmostEqual(result["saturation"]["mean_all_pixels"], sum(saturation) / len(pixels))

    def test_achromatic_hue_denominator_is_null(self):
        result = photo_analysis.measure_pixels(rgb([(0, 0, 0), (255, 255, 255), (127, 127, 127)]))
        hue = result["hue_families"]
        self.assertEqual(hue["achromatic_fraction"], 1)
        self.assertEqual(hue["chromatic_pixels"], 0)
        self.assertTrue(all(s["fraction_of_chromatic_pixels"] is None for s in hue["sectors"]))
        self.assertEqual(result["saturation"]["mean_all_pixels"], 0)
        self.assertEqual(result["color_cast_evidence"]["channel_offsets_from_mean"], [0, 0, 0])
        self.assertIsNone(result["color_cast_evidence"]["cast_verdict"])
        json.dumps(result, allow_nan=False)

    def test_near_gray_is_not_removed_by_a_guessed_threshold(self):
        result = photo_analysis.measure_pixels(rgb([(128, 127, 127), (0, 0, 0)]))
        self.assertEqual(result["hue_families"]["chromatic_pixels"], 1)
        self.assertEqual(result["hue_families"]["sectors"][0]["fraction_of_all_pixels"], 0.5)
        self.assertEqual(result["saturation"]["mean_all_pixels"], 1 / 256)
        self.assertIsNone(result["hue_families"]["minimum_saturation_filter"])

    def test_measured_channel_imbalance_is_not_a_cast_verdict(self):
        result = photo_analysis.measure_pixels(rgb([(255, 0, 0), (255, 0, 0)]))
        evidence = result["color_cast_evidence"]
        self.assertEqual(evidence["mean_rgb"], [255, 0, 0])
        self.assertEqual(evidence["channel_offsets_from_mean"], [170, -85, -85])
        self.assertFalse(evidence["neutral_reference_provided"])
        self.assertIsNone(evidence["cast_verdict"])
        self.assertIsNone(evidence["white_balance_correction"])

    def test_balanced_primary_scene_is_not_declared_neutral(self):
        result = photo_analysis.measure_pixels(rgb([(255, 0, 0), (0, 255, 0), (0, 0, 255)]))
        self.assertEqual(result["color_cast_evidence"]["mean_rgb"], [85, 85, 85])
        self.assertEqual(result["color_cast_evidence"]["channel_offsets_from_mean"], [0, 0, 0])
        self.assertIsNone(result["color_cast_evidence"]["cast_verdict"])

    def test_order_invariant_measurements_and_exact_population(self):
        pixels = [(128, 1, 0), (0, 255, 1), (1, 0, 255), (128, 128, 128)] * 71
        first = photo_analysis.measure_pixels(rgb(pixels))
        last = photo_analysis.measure_pixels(rgb(list(reversed(pixels))))
        for key in ("hue_families", "saturation", "color_cast_evidence"):
            self.assertEqual(first[key], last[key])
        self.assertNotEqual(first["pixel_sha256"], last["pixel_sha256"])
        hue = first["hue_families"]
        self.assertEqual(sum(s["pixels"] for s in hue["sectors"]) + hue["achromatic_pixels"], len(pixels))

    def test_pixel_weighting_counts_duplicates_not_unique_colors(self):
        result = photo_analysis.measure_pixels(rgb([(255, 0, 0)] * 3 + [(0, 255, 0)]))
        self.assertEqual(result["hue_families"]["sectors"][0]["fraction_of_all_pixels"], 0.75)
        self.assertEqual(result["hue_families"]["sectors"][2]["fraction_of_all_pixels"], 0.25)

    def test_input_preserved_and_digest_is_actual_pixel_bytes(self):
        image = rgb([(1, 2, 3), (7, 8, 9)])
        image.info["synthetic"] = "must remain unchanged"
        before = image.tobytes()
        result = photo_analysis.measure_pixels(image)
        self.assertEqual(image.tobytes(), before)
        self.assertEqual(image.info, {"synthetic": "must remain unchanged"})
        self.assertEqual(result["pixel_sha256"], hashlib.sha256(before).hexdigest())
        self.assertEqual(result["dimensions"], [2, 1])

    def test_invalid_modes_and_empty_images(self):
        for image in (None, [], Image.new("RGB", (0, 1)), Image.new("L", (1, 1)),
                      Image.new("RGBA", (1, 1)), Image.new("P", (1, 1))):
            with self.subTest(image=type(image)), self.assertRaises(InputError):
                photo_analysis.measure_pixels(image)


class AnalysisCliTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix=".analysis-test-", dir=HERE)
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root / "synthetic-private-person-location.png"
        self.image = rgb([(255, 0, 0), (0, 255, 0), (0, 0, 255)])
        self.image.save(self.source)

    def cli(self, *options):
        return subprocess.run([sys.executable, "-B", str(HERE / "cinegrade.py"),
                               "analyze", str(self.source), *options],
                              capture_output=True, text=True, timeout=30)

    def test_cli_complete_json_and_read_only_repeatability(self):
        before = self.source.read_bytes()
        files = set(self.root.iterdir())
        first, second = self.cli("--assume-srgb"), self.cli("--assume-srgb")
        self.assertEqual(first.returncode, 0, first.stderr)
        self.assertEqual(second.returncode, 0, second.stderr)
        self.assertEqual(first.stdout, second.stdout)
        report = json.loads(first.stdout)
        self.assertEqual(report["schema"], "cinegrade-analysis/1")
        self.assertEqual(report["status"], "complete")
        self.assertEqual(report["input"]["source_sha256"], hashlib.sha256(before).hexdigest())
        self.assertEqual(report["measurements"]["pixel_count"], 3)
        self.assertFalse(report["selection"]["automatic_selection"])
        self.assertIsNone(report["selection"]["ranked_looks"])
        self.assertIn("skin_fraction", report["pending"])
        self.assertIn("untagged_source_assumed_srgb", report["warnings"])
        self.assertEqual(self.source.read_bytes(), before)
        self.assertEqual(set(self.root.iterdir()), files)
        self.assertNotIn(self.source.name, first.stdout)
        self.assertNotIn(str(self.root), first.stdout)

    def test_untagged_input_requires_confirmation(self):
        result = self.cli()
        self.assertEqual(result.returncode, 2)
        self.assertEqual(result.stdout, "")
        self.assertNotIn("Traceback", result.stderr)
        self.assertNotIn(self.source.name, result.stderr)

    def test_tagged_icc_orientation_and_private_metadata(self):
        exif = Image.Exif()
        exif[274] = 6
        exif[315] = "SYNTHETIC_PRIVATE_OWNER"
        exif[42033] = "SYNTHETIC_SERIAL"
        meta = PngImagePlugin.PngInfo()
        meta.add_text("Comment", "SYNTHETIC_PRIVATE_PLACE")
        profile = ImageCms.ImageCmsProfile(ImageCms.createProfile("sRGB")).tobytes()
        self.image.save(self.source, icc_profile=profile, exif=exif, pnginfo=meta)
        result = self.cli()
        self.assertEqual(result.returncode, 0, result.stderr)
        report = json.loads(result.stdout)
        self.assertEqual(report["input"]["color_management"]["action"], "icc_to_srgb")
        self.assertEqual(report["measurements"]["dimensions"], [1, 3])
        self.assertEqual(report["input"]["orientation_applied"], 6)
        self.assertEqual(report["measurements"]["pixel_sha256"], hashlib.sha256(self.image.tobytes()).hexdigest())
        for secret in ("SYNTHETIC_PRIVATE_OWNER", "SYNTHETIC_SERIAL", "SYNTHETIC_PRIVATE_PLACE", self.source.name):
            self.assertNotIn(secret, result.stdout)

    def test_loader_snapshot_is_consumed_once_without_redecode(self):
        loaded = LoadedImage(rgb([(0, 255, 255)]), {"warnings": [], "source_sha256": "synthetic-test-snapshot"})
        with mock.patch.object(photo_analysis, "load_image", return_value=loaded) as loader:
            report = photo_analysis.analyze(self.source, assume_srgb=True)
        loader.assert_called_once_with(self.source, assume_srgb=True)
        self.assertEqual(report["measurements"]["hue_families"]["sectors"][3]["pixels"], 1)

    def test_corrupt_icc_cannot_fall_back_to_assumption(self):
        self.image.save(self.source, icc_profile=b"synthetic-invalid-profile")
        result = self.cli("--assume-srgb")
        self.assertEqual(result.returncode, 2)
        self.assertEqual(result.stdout, "")
        self.assertNotIn("Traceback", result.stderr)

    def test_unsupported_alpha_and_missing_source_fail_safely(self):
        Image.new("RGBA", (1, 1)).save(self.source)
        result = self.cli("--assume-srgb")
        self.assertEqual(result.returncode, 2)
        self.assertEqual(result.stdout, "")
        self.source.unlink()
        result = self.cli("--assume-srgb")
        self.assertEqual(result.returncode, 2)
        self.assertEqual(result.stdout, "")
        self.assertNotIn(self.source.name, result.stderr)

    def test_cli_has_no_output_or_automatic_correction_options(self):
        for options in (("--output", str(self.source)), ("--strength", "50")):
            result = self.cli("--assume-srgb", *options)
            self.assertEqual(result.returncode, 2)
            self.assertEqual(result.stdout, "")
        self.assertEqual(set(self.root.iterdir()), {self.source})


if __name__ == "__main__":
    unittest.main()
