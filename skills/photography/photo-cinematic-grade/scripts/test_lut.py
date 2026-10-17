# SYNTHETIC mathematical/CLI fixtures, not photographs, measured scenes or
# user-confirmed creative parameters. All constructed colors, permutations,
# strengths, paths and fault injections exist solely to test the stated API.
# Existing bundled recipes are read unchanged; no new look is invented here.
import contextlib
import hashlib
import io
import itertools
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

import numpy as np
from PIL import Image, PngImagePlugin

import cinegrade
import cinegrade_lut as lut
import image_io

HERE = Path(__file__).resolve().parent


class LutTests(unittest.TestCase):
    def setUp(self):
        local = HERE.parents[3] / ".git"
        self.temp = tempfile.TemporaryDirectory(dir=local if local.is_dir() else None)
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root / "synthetic-private-source.png"
        # SYNTHETIC grayscale ramp plus channel-shifted ramps; endpoints included.
        axis = np.arange(256, dtype=np.uint8)
        rgb = np.stack((axis, np.roll(axis, 64), np.roll(axis, 128)), axis=-1)
        self.image = Image.frombytes("RGB", (256, 1), rgb.tobytes())
        self.image.save(self.source)

    def test_identity_all_codes_and_corners(self):
        values = np.arange(256, dtype=np.float64) / 255
        colors = np.stack((values, values[::-1], values), axis=-1)
        for size in (2, 33, 65):
            actual = lut.tetrahedral(lut.identity_table(size), colors)
            np.testing.assert_allclose(actual, colors, rtol=0, atol=3e-16)
            corners = np.array(list(itertools.product((0., 1.), repeat=3)))
            np.testing.assert_array_equal(lut.tetrahedral(lut.identity_table(size), corners), corners)

    def test_affine_channel_permutation(self):
        grid = lut.identity_table(3)
        table = grid[..., [2, 0, 1]] / 2 + 0.25  # SYNTHETIC exact affine transform.
        colors = np.array([[0.9, 0.1, 0.7], [0, 1, 0.5], [1, 1, 1]])
        np.testing.assert_allclose(lut.tetrahedral(table, colors), colors[:, [2, 0, 1]] / 2 + 0.25,
                                   rtol=0, atol=3e-16)

    def test_six_tetrahedra_against_hand_vertex_means(self):
        # Hand-enumerated paths in RED/GREEN/BLUE vertex coordinates. At local
        # sorted fractions 3/4, 1/2, 1/4 all four barycentric weights are 1/4.
        paths = [
            ((.75, .5, .25), [(0,0,0),(1,0,0),(1,1,0),(1,1,1)]),
            ((.75, .25, .5), [(0,0,0),(1,0,0),(1,0,1),(1,1,1)]),
            ((.5, .25, .75), [(0,0,0),(0,0,1),(1,0,1),(1,1,1)]),
            ((.5, .75, .25), [(0,0,0),(0,1,0),(1,1,0),(1,1,1)]),
            ((.25, .75, .5), [(0,0,0),(0,1,0),(0,1,1),(1,1,1)]),
            ((.25, .5, .75), [(0,0,0),(0,0,1),(0,1,1),(1,1,1)]),
        ]
        # Non-affine corner values ensure trilinear interpolation cannot pass.
        table = np.array([0, 1, 4, 2, 7, 3, 6, 5], dtype=float).reshape(2,2,2) / 8
        table = np.repeat(table[..., None], 3, axis=-1)
        for color, vertices in paths:
            expected = sum(table[b,g,r] for r,g,b in vertices) / 4
            np.testing.assert_array_equal(lut.tetrahedral(table, color), expected)

    def test_tetrahedral_is_not_trilinear(self):
        table = np.zeros((2,2,2,3))
        table[1,1,1] = 1
        actual = lut.tetrahedral(table, [.75, .5, .25])
        np.testing.assert_array_equal(actual, [.25] * 3)
        self.assertNotEqual(float(actual[0]), .75 * .5 * .25)

    def test_ties_and_closed_upper_boundary(self):
        table = np.zeros((2,2,2,3))
        table[1,1,1] = 1
        for rgb in ([.5,.5,.25], [.5,.25,.5], [.25,.5,.5], [.5]*3, [1]*3, [1,0,1]):
            np.testing.assert_allclose(lut.tetrahedral(table, rgb), [min(rgb)] * 3, rtol=0, atol=1e-16)
        for side in (np.nextafter(.5, 0), np.nextafter(.5, 1)):
            np.testing.assert_allclose(lut.tetrahedral(table, [side,.5,.25]), [.25]*3, rtol=0, atol=1e-16)

    def test_handwritten_cube_red_fastest(self):
        blob = (b"# SYNTHETIC identity, explicit standard row order\nLUT_3D_SIZE 2\n"
                b"0 0 0\n1 0 0\n0 1 0\n1 1 0\n0 0 1\n1 0 1\n0 1 1\n1 1 1\n")
        parsed = lut.decode_cube(blob)
        np.testing.assert_array_equal(parsed[0,0,1], [1,0,0])
        np.testing.assert_array_equal(parsed[1,0,0], [0,0,1])
        np.testing.assert_array_equal(lut.tetrahedral(parsed, [.25,.5,.75]), [.25,.5,.75])

    def test_serialization_exact_and_repeatable(self):
        table = lut.identity_table(7)
        blob = lut.encode_cube(table)
        np.testing.assert_array_equal(lut.decode_cube(blob), table)
        self.assertEqual(blob, lut.encode_cube(table))
        self.assertIn(b"LUT_3D_SIZE 7\n", blob)
        self.assertEqual(len([s for s in blob.splitlines() if s[:1].isdigit()]), 7**3)

    def test_parser_rejects_bad_count_directive_domain_and_values(self):
        good = lut.encode_cube(lut.identity_table(2))
        bad = [b"", good[:-6], good + b"0 0 0\n", good + b"LUT_3D_SIZE 2\n",
               good.replace(b"LUT_3D_SIZE 2", b"LUT_3D_SIZE 1"),
               good.replace(b"LUT_3D_SIZE 2", b"LUT_3D_SIZE 66"),
               good.replace(b"LUT_3D_SIZE 2", b"LUT_3D_SIZE 2.0"),
               good.replace(b"DOMAIN_MIN 0 0 0", b"DOMAIN_MIN -1 0 0"),
               good.replace(b"DOMAIN_MAX 1 1 1", b"DOMAIN_MAX 1 1 nan"),
               good.replace(b"DOMAIN_MAX 1 1 1", b"DOMAIN_MAX 1 1"),
               good.replace(b"DOMAIN_MIN 0 0 0", b"DOMAIN_MIN 0 0 0\nDOMAIN_MIN 0 0 0"),
               b"LUT_1D_SIZE 2\n" + good, b"TITLE arbitrary\n" + good,
               good.replace(b"0 0 0\n1 0 0", b"nan 0 0\n1 0 0"),
               good.replace(b"0 0 0\n1 0 0", b"-0.01 0 0\n1 0 0"),
               good.replace(b"1 1 1\n", b"1 1 inf\n"), b"\xff", "not bytes"]
        for blob in bad:
            with self.subTest(blob=repr(blob)[:80]), self.assertRaises(image_io.InputError):
                lut.decode_cube(blob)

    def test_invalid_arrays_sizes_and_no_silent_clipping(self):
        identity = lut.identity_table(2)
        for size in (0, 1, 66, True, 3.0, "33"):
            with self.assertRaises(image_io.InputError):
                lut.identity_table(size)
        for color in ([], 1, [0,1], [0,0,float("nan")], [0,0,float("inf")],
                      [False]*3, ["0"]*3, [0,0,1j], [-1e-20,0,0], [0,0,np.nextafter(1.,2.)]):
            with self.subTest(color=color), self.assertRaises(image_io.InputError):
                lut.tetrahedral(identity, color)
        for table in (np.zeros((2,3,2,3)), np.zeros((1,1,1,3)), [[0,0,0]], identity + 1):
            with self.assertRaises(image_io.InputError):
                lut.encode_cube(table)

    def test_noncontiguous_readonly_and_input_immutability(self):
        table = lut.identity_table(3)
        table.setflags(write=False)
        colors = np.arange(24, dtype=float).reshape(2,4,3) / 24
        view = colors.transpose(1,0,2)
        view.setflags(write=False)
        original = view.copy()
        actual = lut.tetrahedral(table, view)
        np.testing.assert_allclose(actual, original, rtol=0, atol=3e-16)
        np.testing.assert_array_equal(view, original)
        self.assertFalse(np.shares_memory(actual, view))

    def test_zero_strength_identity_and_invalid_strength(self):
        recipe = cinegrade.load_looks()["warm-muted"]
        np.testing.assert_array_equal(lut.legacy_table(recipe, 0), lut.identity_table())
        for strength in (-1,101,True,1.5):
            with self.assertRaises(image_io.InputError):
                lut.legacy_table(recipe, strength)

    def test_existing_renderer_matches_every_sampled_node(self):
        grid = lut.identity_table()
        code = np.floor(grid.reshape(-1,3) * 255 + .5).astype(np.uint8)
        image = Image.frombytes("RGB", (33*33,33), code.tobytes())
        for recipe in cinegrade.load_looks().values():
            direct, _ = cinegrade.grade_pixels(image, recipe, 100)
            table = lut.legacy_table(recipe, 100)
            np.testing.assert_array_equal(table.reshape(-1,3), np.asarray(direct).reshape(-1,3) / 255)

    def test_qa_all_pixels_batch_independent_and_identity(self):
        table = lut.identity_table()
        one = lut.roundtrip_qa(table, self.image, self.image)
        with mock.patch.object(lut, "QA_BATCH", 7):
            batched = lut.roundtrip_qa(table, self.image, self.image)
        self.assertEqual(one, batched)
        self.assertEqual(one["pixels_evaluated"], 256)
        self.assertLess(one["max"], 1e-14)
        self.assertEqual(one["visual_acceptance"], "not_evaluated")
        self.assertFalse(one["lut_output_quantized"])

    def test_fixed_order_qa_conversion_matches_published_core(self):
        from color_core import linear_srgb_to_oklab, srgb_to_linear
        # SYNTHETIC full unit grid; converter comparison is numerical only.
        colors = lut.identity_table(9).reshape(-1,3)
        np.testing.assert_allclose(lut._lab_for_qa(colors),
                                   linear_srgb_to_oklab(srgb_to_linear(colors)), rtol=0, atol=1e-14)

    def test_qa_rejects_mismatched_or_non_rgb_images(self):
        for other in (Image.new("RGB", (2,2)), Image.new("L", self.image.size), None):
            with self.assertRaises(image_io.InputError):
                lut.roundtrip_qa(lut.identity_table(), self.image, other)

    def test_p99_guard_is_strict_at_plan_boundary(self):
        self.assertTrue(lut.summarize_errors([np.nextafter(.02, 0)])["pass"])
        self.assertFalse(lut.summarize_errors([.02])["pass"])
        self.assertFalse(lut.summarize_errors([np.nextafter(.02, 1)])["pass"])
        summary = lut.summarize_errors([0,.01,.02])
        self.assertAlmostEqual(summary["p99"], .0198)
        for errors in ([], [-1], [float("nan")], [float("inf")], [True], [[0]], ["0"]):
            with self.assertRaises(image_io.InputError):
                lut.summarize_errors(errors)

    def test_bad_lut_fails_real_color_measurement(self):
        qa = lut.roundtrip_qa(np.zeros((2,2,2,3)), self.image, self.image)
        self.assertFalse(qa["pass"])
        self.assertGreater(qa["p99"], .02)

    def test_export_three_existing_looks_and_reproducibility(self):
        for look in cinegrade.load_looks():
            report = lut.export_lut(self.source, self.root/look, look=look, strength=100, assume_srgb=True)
            self.assertEqual(report["status"], "complete")
            self.assertTrue(report["qa"]["pass"])
            self.assertEqual(report["qa"]["pixels_evaluated"], 256)
            disk = (self.root/look/"grade.cube").read_bytes()
            self.assertEqual(report["output"]["cube_sha256"], hashlib.sha256(disk).hexdigest())
            self.assertEqual(report, json.loads((self.root/look/"report.json").read_text()))
            self.assertEqual(lut.decode_cube(disk).shape, (33,33,33,3))
        lut.export_lut(self.source, self.root/"repeat", look="warm-muted", strength=100, assume_srgb=True)
        self.assertEqual((self.root/"repeat"/"grade.cube").read_bytes(),
                         (self.root/"warm-muted"/"grade.cube").read_bytes())

    def test_export_no_overwrite_and_no_source_change(self):
        before = self.source.read_bytes()
        existing = self.root/"existing"
        existing.mkdir()
        alias = self.root/"alias"
        alias.symlink_to(existing, target_is_directory=True)
        dangling = self.root/"dangling"
        dangling.symlink_to(self.root/"missing")
        for target in (self.source, existing, alias, dangling, self.root):
            with self.assertRaises(image_io.InputError):
                lut.export_lut(self.source, target, look="neutral", strength=0, assume_srgb=True)
        self.assertEqual(self.source.read_bytes(), before)
        self.assertEqual(list(existing.iterdir()), [])
        self.assertTrue(dangling.is_symlink())

    def test_export_bad_parameters_before_source_read(self):
        with mock.patch.object(lut, "load_image") as load:
            for look, strength in (("missing",0),([],0),("neutral",True),("neutral",101)):
                with self.assertRaises(image_io.InputError):
                    lut.export_lut(self.source, self.root/"out", look=look, strength=strength)
            load.assert_not_called()
        self.assertFalse((self.root/"out").exists())

    def test_color_input_refusal_without_output(self):
        with self.assertRaises(image_io.InputError):
            lut.export_lut(self.source, self.root/"out", look="neutral", strength=0)
        self.assertFalse((self.root/"out").exists())
        self.image.save(self.source, icc_profile=b"SYNTHETIC_BAD_ICC")
        with self.assertRaises(image_io.InputError):
            lut.export_lut(self.source, self.root/"out", look="neutral", strength=0, assume_srgb=True)
        self.assertFalse((self.root/"out").exists())

    def test_privacy_orientation_and_tagged_source(self):
        exif = Image.Exif()
        exif[274] = 6
        exif[315] = "SYNTHETIC_PRIVATE_OWNER"
        exif[34853] = {1:"N", 2:(31.,13.,0.)}
        info = PngImagePlugin.PngInfo()
        info.add_text("Comment", "SYNTHETIC_PRIVATE_LOCATION")
        self.image.save(self.source, exif=exif, pnginfo=info)
        report = lut.export_lut(self.source, self.root/"private", look="neutral", strength=0, assume_srgb=True)
        self.assertEqual(report["input"]["oriented_dimensions"], [1,256])
        text = (self.root/"private"/"report.json").read_text()
        for secret in ("SYNTHETIC_PRIVATE", self.source.name, str(self.root), "GPS"):
            self.assertNotIn(secret, text)
            self.assertNotIn(secret.encode(), (self.root/"private"/"grade.cube").read_bytes())
        self.source.write_bytes(image_io.encode_png(self.image))
        report = lut.export_lut(self.source, self.root/"tagged", look="neutral", strength=0)
        self.assertEqual(report["input"]["color_management"]["action"], "icc_to_srgb")

    def test_disk_failure_retains_partial_without_receipt(self):
        target = self.root/"partial"
        real_write = lut._write_bytes
        def fail(path, data):
            if path.name == "grade.cube":
                real_write(path, data[:20])
                raise OSError("SYNTHETIC disk full")
            real_write(path, data)
        with mock.patch.object(lut, "_write_bytes", side_effect=fail), self.assertRaises(image_io.InputError):
            lut.export_lut(self.source, target, look="neutral", strength=0, assume_srgb=True)
        self.assertEqual((target/"grade.cube").stat().st_size, 20)
        self.assertFalse((target/"report.json").exists())

    def test_tampered_disk_readback_never_publishes_receipt(self):
        real_read = Path.read_bytes
        target = self.root/"tampered"
        def tamper(path):
            data = real_read(path)
            return data + b"# SYNTHETIC tamper\n" if path.name == "grade.cube" else data
        with mock.patch.object(Path, "read_bytes", tamper), self.assertRaises(image_io.InputError):
            lut.export_lut(self.source, target, look="neutral", strength=0, assume_srgb=True)
        self.assertTrue((target/"grade.cube").exists())
        self.assertFalse((target/"report.json").exists())

    def test_receipt_publish_failure_keeps_cube_and_pending(self):
        target = self.root/"publish-fault"
        with mock.patch.object(lut.os, "link", side_effect=OSError("SYNTHETIC publication fault")):
            with self.assertRaises(image_io.InputError):
                lut.export_lut(self.source, target, look="neutral", strength=0, assume_srgb=True)
        self.assertTrue((target/"grade.cube").exists())
        self.assertTrue((target/".report.pending").exists())
        self.assertFalse((target/"report.json").exists())

    def test_cli_required_inputs_and_real_success(self):
        base = [sys.executable, "-B", str(HERE/"cinegrade.py"), "lut", str(self.source)]
        for flags in ([], ["--look","neutral"], ["--strength","0"],
                      ["--look","neutral","--strength","101","--assume-srgb"],
                      ["--look","neutral","--strength","0"]):
            proc = subprocess.run(base + ["--output",str(self.root/"bad")] + flags,
                                  capture_output=True, text=True, timeout=30)
            self.assertEqual(proc.returncode, 2, proc.stderr)
            self.assertNotIn("Traceback", proc.stderr)
            self.assertFalse((self.root/"bad").exists())
        proc = subprocess.run(base + ["--output",str(self.root/"cli"),"--look","warm-muted",
                                      "--strength","100","--assume-srgb"],
                              capture_output=True, text=True, timeout=30)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        summary = json.loads(proc.stdout)
        self.assertEqual(summary["status"], "complete")
        self.assertTrue(summary["qa"]["pass"])
        self.assertNotIn(str(self.root), proc.stdout)
        self.assertNotIn(self.source.name, proc.stdout)

    def test_cli_real_qa_failure_exits_one_and_keeps_evidence(self):
        # SYNTHETIC broken transform injection. The QA is REAL, not mocked green.
        target = self.root/"failed-qa"
        stdout = io.StringIO()
        with mock.patch.object(lut, "legacy_table", return_value=np.zeros((33,33,33,3))):
            with contextlib.redirect_stdout(stdout):
                result = cinegrade.main(["lut",str(self.source),"--output",str(target),
                                         "--look","neutral","--strength","0","--assume-srgb"])
        self.assertEqual(result, 1)
        summary = json.loads(stdout.getvalue())
        self.assertEqual(summary["status"], "qa_failed")
        self.assertFalse(summary["qa"]["pass"])
        self.assertGreater(summary["qa"]["p99"], .02)
        self.assertTrue((target/"grade.cube").exists())
        self.assertEqual(json.loads((target/"report.json").read_text())["status"], "qa_failed")


if __name__ == "__main__":
    unittest.main(verbosity=2)
