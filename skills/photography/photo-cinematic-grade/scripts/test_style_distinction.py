# SYNTHETIC mathematical/CLI fixtures only. Arrays, images, strengths and faults
# are constructed in this file to test software; none are real photographs or
# photographer-confirmed creative recipes. Color constants below are the
# published Oklab matrices, not invented observations. No visual acceptance.
import hashlib
import json
import math
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

import numpy as np
from PIL import Image

import cinegrade
from image_io import InputError
import style_distinction as sd

HERE = Path(__file__).resolve().parent


def scalar_lab(rgb):
    # Independent scalar oracle using the published D65 Oklab matrix equations
    # (bottosson.github.io/posts/oklab/), not the production conversion functions.
    linear = [x / 12.92 if x <= 0.04045 else ((x + 0.055) / 1.055) ** 2.4 for x in rgb]
    lms = [[0.4122214708, 0.5363325363, 0.0514459929],
           [0.2119034982, 0.6806995451, 0.1073969566],
           [0.0883024619, 0.2817188376, 0.6299787005]]
    roots = [sum(x * y for x, y in zip(row, linear)) ** (1 / 3) for row in lms]
    lab = [[0.2104542553, 0.7936177850, -0.0040720468],
           [1.9779984951, -2.4285922050, 0.4505937099],
           [0.0259040371, 0.7827717662, -0.8086757660]]
    return [sum(x * y for x, y in zip(row, roots)) for row in lab]


def scalar_distance(first, second):
    return math.sqrt(sum((x - y) ** 2 for x, y in zip(scalar_lab(first), scalar_lab(second))))


class DistinctionTests(unittest.TestCase):
    def setUp(self):
        # SYNTHETIC 2x3 RGB primary/end-point chart, not measured scene data.
        self.source = np.array([[[0, 0, 0], [1, 1, 1], [1, 0, 0]],
                                [[0, 1, 0], [0, 0, 1], [0.5, 0.5, 0.5]]], dtype=float)

    def qa(self, styles=None, vivid=()):
        return sd.style_distinction_qa(self.source, {"a": self.source} if styles is None else styles,
                                       vivid_styles=vivid)

    def test_identity_is_exact_and_not_global_acceptance(self):
        result = self.qa(vivid=["a"])
        check = result["original_comparisons"][0]
        self.assertEqual(check["mean_delta_e_ok"], 0)
        self.assertFalse(check["pass"])
        self.assertNotIn("pass", result)
        self.assertIn("vivid_style_below_original_distinction:a", result["warnings"])

    def test_original_minimum_only_applies_to_declared_vivid_styles(self):
        result = self.qa({"muted": self.source, "vivid": self.source}, ["vivid"])
        muted, vivid = result["original_comparisons"]
        self.assertIsNone(muted["pass"])
        self.assertFalse(muted["meets_reference"])
        self.assertFalse(muted["criterion_applicable"])
        self.assertFalse(vivid["pass"])
        self.assertNotIn("vivid_style_below_original_distinction:muted", result["warnings"])

    def test_known_black_white_and_primaries_scalar_oracle(self):
        changed = 1 - self.source
        result = self.qa({"inverse": changed}, ["inverse"])
        expected = sum(scalar_distance(a, b) for a, b in zip(self.source.reshape(-1, 3), changed.reshape(-1, 3))) / 6
        self.assertAlmostEqual(result["original_comparisons"][0]["mean_delta_e_ok"], expected, places=13)
        self.assertTrue(result["original_comparisons"][0]["pass"])

    def test_mean_of_distances_does_not_cancel_swapped_colors(self):
        source = np.array([[[1., 0, 0], [0, 0, 1.]]])
        swapped = source[:, ::-1]
        result = sd.style_distinction_qa(source, {"swap": swapped}, vivid_styles=[])
        distance = result["original_comparisons"][0]["mean_delta_e_ok"]
        self.assertAlmostEqual(distance, scalar_distance(source[0, 0], source[0, 1]), places=13)
        self.assertGreater(distance, 0)

    def test_all_pixels_count_dimensions_and_equal_weight(self):
        changed = self.source.copy()
        changed[0, 0] = 1
        result = self.qa({"one": changed})
        self.assertEqual(result["pixel_count"], 6)
        self.assertEqual(result["dimensions"], [3, 2])
        self.assertTrue(result["all_supplied_pixels"])
        self.assertAlmostEqual(result["original_comparisons"][0]["mean_delta_e_ok"], scalar_distance([0, 0, 0], [1, 1, 1]) / 6, places=13)

    def test_inclusive_threshold_and_immediate_float_neighbors(self):
        for limit in (sd.ORIGINAL_MINIMUM, sd.PAIR_MINIMUM):
            self.assertTrue(sd._criterion(limit, limit, True)["pass"])
            self.assertFalse(sd._criterion(float(np.nextafter(limit, 0)), limit, True)["pass"])
            self.assertTrue(sd._criterion(float(np.nextafter(limit, 1)), limit, True)["pass"])
        self.assertEqual(sd.ORIGINAL_MINIMUM, 0.035)
        self.assertEqual(sd.PAIR_MINIMUM, 0.025)

    def test_every_unordered_pair_once_in_input_order(self):
        names = ["d", "b", "a", "c"]
        result = self.qa({x: self.source for x in names})
        expected = [["d", "b"], ["d", "a"], ["d", "c"], ["b", "a"], ["b", "c"], ["a", "c"]]
        self.assertEqual([p["styles"] for p in result["pairwise_comparisons"]], expected)
        self.assertTrue(all(p["pass"] is False for p in result["pairwise_comparisons"]))

    def test_pairwise_measures_both_styles_not_source(self):
        black = np.zeros_like(self.source)
        white = np.ones_like(self.source)
        result = self.qa({"black": black, "white": white})
        pair = result["pairwise_comparisons"][0]
        self.assertAlmostEqual(pair["mean_delta_e_ok"], scalar_distance([0, 0, 0], [1, 1, 1]), places=13)
        self.assertTrue(pair["pass"])
        self.assertEqual(result["warnings"], [])

    def test_single_style_reports_missing_pairwise_evidence(self):
        result = self.qa()
        self.assertEqual(result["pairwise_comparisons"], [])
        self.assertIn("pairwise_distinction_not_evaluated_fewer_than_two_styles", result["warnings"])

    def test_noncontiguous_readonly_inputs_unchanged(self):
        source = self.source[:, ::-1]
        changed = (1 - self.source)[:, ::-1]
        source.flags.writeable = False
        changed.flags.writeable = False
        before = source.tobytes(), changed.tobytes()
        result = sd.style_distinction_qa(source, {"a": changed}, vivid_styles=[])
        contiguous = sd.style_distinction_qa(source.copy(), {"a": changed.copy()}, vivid_styles=[])
        self.assertEqual(result, contiguous)
        self.assertEqual(before, (source.tobytes(), changed.tobytes()))

    def test_reproducible_strict_json(self):
        first = self.qa({"a": 1 - self.source})
        second = self.qa({"a": 1 - self.source})
        self.assertEqual(json.dumps(first, allow_nan=False, sort_keys=True), json.dumps(second, allow_nan=False, sort_keys=True))

    def test_reject_invalid_array_types_and_shapes(self):
        for bad in (None, True, "rgb", [], np.zeros((0, 2, 3)), np.zeros((2, 3)),
                    np.zeros((1, 2, 4)), np.ones((1, 1, 3), dtype=bool),
                    np.ones((1, 1, 3), dtype=complex), [[["0", "1", "0"]]]):
            with self.subTest(shape=str(type(bad))), self.assertRaises(InputError):
                sd.style_distinction_qa(bad, {"a": self.source}, vivid_styles=[])

    def test_reject_nonfinite_and_out_of_gamut_without_clamping(self):
        for value in (float("nan"), float("inf"), -float("inf"), np.nextafter(0., -1.), np.nextafter(1., 2.), 255):
            bad = self.source.copy()
            bad[0, 0, 0] = value
            with self.subTest(value=value), self.assertRaises(InputError):
                self.qa({"a": bad})

    def test_reject_mismatched_dimensions_without_resizing(self):
        with self.assertRaises(InputError):
            self.qa({"a": self.source.transpose(1, 0, 2)})

    def test_reject_missing_styles_and_unsafe_identifiers(self):
        for bad in ({}, [], {"": self.source}, {"a/b": self.source}, {"A": self.source}, {1: self.source}):
            with self.subTest(bad_type=str(type(bad))), self.assertRaises(InputError):
                self.qa(bad)

    def test_require_explicit_unique_present_vivid_ids(self):
        for bad in (None, "a", {"a"}, [1], ["missing"], ["a", "a"]):
            with self.subTest(bad=str(bad)), self.assertRaises(InputError):
                self.qa(vivid=bad)


class CandidateDistinctionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix=".distinction-test-", dir=HERE)
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        # SYNTHETIC ramp, test dimensions and strength. No real photo/recipe claim.
        self.image = Image.fromarray(np.arange(72, dtype=np.uint8).reshape(4, 6, 3))
        self.source = self.root / "synthetic-private-name.png"
        self.image.save(self.source)
        self.source_hash = hashlib.sha256(self.source.read_bytes()).hexdigest()

    def candidates(self, name="out", **options):
        return cinegrade.candidates(self.source, self.root / name, assume_srgb=True, **options)

    def test_opt_in_preserves_existing_pixels_records_and_source(self):
        legacy = self.candidates("legacy")
        measured = self.candidates("measured", distinction_qa=True)
        self.assertNotIn("style_distinction", legacy["qa"])
        self.assertEqual(legacy["candidates"], measured["candidates"])
        for item in legacy["candidates"]:
            filename = item["output"]["file"]
            self.assertEqual((self.root / "legacy" / filename).read_bytes(), (self.root / "measured" / filename).read_bytes())
        qa = measured["qa"]["style_distinction"]
        self.assertEqual(qa["vivid_styles"], [])
        self.assertTrue(all(x["pass"] is None for x in qa["original_comparisons"]))
        self.assertEqual([x["style"] for x in qa["original_comparisons"]], ["warm-muted", "cool-muted"])
        self.assertEqual(hashlib.sha256(self.source.read_bytes()).hexdigest(), self.source_hash)

    def test_measurements_match_written_pngs_and_resized_scope(self):
        report = self.candidates(distinction_qa=True, max_edge=3)
        arrays = {}
        for item in report["candidates"]:
            with Image.open(self.root / "out" / item["output"]["file"]) as image:
                arrays[item["grade"]["look"]] = np.asarray(image, dtype=float) / 255
        expected = sd.style_distinction_qa(arrays.pop("neutral"), arrays, vivid_styles=[])
        actual = report["qa"]["style_distinction"]
        self.assertEqual(actual["pixel_count"], 6)
        self.assertEqual(actual["scope"], "resized_preview_only")
        self.assertEqual(actual["original_comparisons"], expected["original_comparisons"])
        self.assertEqual(actual["pairwise_comparisons"], expected["pairwise_comparisons"])
        self.assertEqual(json.loads((self.root / "out" / "report.json").read_text()), report)

    def test_zero_strength_reports_collapsed_pair_without_vivid_claim(self):
        report = self.candidates(strength=0, distinction_qa=True)
        qa = report["qa"]["style_distinction"]
        self.assertEqual(qa["pairwise_comparisons"][0]["mean_delta_e_ok"], 0)
        self.assertFalse(qa["pairwise_comparisons"][0]["pass"])
        self.assertEqual(qa["warnings"], ["styles_below_pairwise_distinction:warm-muted:cool-muted"])
        self.assertFalse(report["selection"]["automatic_selection"])

    def test_numeric_failure_before_output_reservation(self):
        with mock.patch.object(sd, "style_distinction_qa", side_effect=InputError("synthetic QA failure")):
            with self.assertRaises(InputError):
                self.candidates(distinction_qa=True)
        self.assertFalse((self.root / "out").exists())

    def test_output_and_original_are_never_replaced(self):
        self.candidates(distinction_qa=True)
        before = (self.root / "out" / "report.json").read_bytes()
        with self.assertRaises(InputError):
            self.candidates(distinction_qa=True)
        with self.assertRaises(InputError):
            cinegrade.candidates(self.source, self.source, assume_srgb=True, distinction_qa=True)
        self.assertEqual(before, (self.root / "out" / "report.json").read_bytes())
        self.assertEqual(hashlib.sha256(self.source.read_bytes()).hexdigest(), self.source_hash)

    def test_incomplete_write_has_no_final_report(self):
        target = self.root / "out"
        real_open = Path.open
        def fail_receipt(path, *args, **kwargs):
            if path.parent == target and path.name == ".report.pending":
                raise OSError("synthetic disk full")
            return real_open(path, *args, **kwargs)
        with mock.patch.object(Path, "open", fail_receipt), self.assertRaises(InputError):
            self.candidates(distinction_qa=True)
        self.assertFalse((target / "report.json").exists())
        self.assertEqual(len(list(target.glob("*.png"))), 3)

    def test_cli_surfaces_pair_warning_and_retains_completed_output(self):
        proc = subprocess.run([sys.executable, "-B", str(HERE / "cinegrade.py"), "candidates", str(self.source),
            "--output", str(self.root / "cli"), "--assume-srgb", "--strength", "0", "--distinction-qa"],
            capture_output=True, text=True, timeout=30)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        summary = json.loads(proc.stdout)
        self.assertEqual(summary["status"], "complete")
        self.assertIn("styles_below_pairwise_distinction:warm-muted:cool-muted", summary["warnings"])
        self.assertNotIn(self.source.name, proc.stdout)
        self.assertNotIn(str(self.root), proc.stdout)
        self.assertTrue((self.root / "cli" / "report.json").is_file())


if __name__ == "__main__":
    unittest.main(verbosity=2)
