"""SYNTHETIC CDP dictionaries for a real hosted-macOS font-name regression.

The positive pair was observed in GitHub Actions run 38882554956. Negative
fixtures are deliberately invented unit inputs, not measured browser results.
No font or render acceptance threshold is changed by these tests.
"""
import sys
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "skills/coding-helper/bento-infographic/scripts"
sys.path.insert(0, str(SCRIPTS))
import bento_render as br


class PlatformFontIdentityTests(unittest.TestCase):
    def test_observed_localized_pair_has_stable_canonical_family(self):
        font = {"familyName": "蘋方-簡", "postScriptName": "PingFangSC-Semibold"}
        self.assertEqual(br.platform_font_family(font), "PingFang SC")
        self.assertEqual(font["familyName"], "蘋方-簡")

    def test_alias_without_postscript_identity_is_not_accepted(self):
        for face in (None, "", "Times-Roman", "PingFangTC-Semibold", "PingFangSC-Fake", "PingFangSC-Semibold-Evil"):
            with self.subTest(face=face):
                self.assertEqual(br.platform_font_family({"familyName": "蘋方-簡", "postScriptName": face}), "蘋方-簡")

    def test_conflicting_or_unknown_family_stays_unrecognized(self):
        for family in ("Times", "蘋方-繁", "Unknown", None):
            with self.subTest(family=family):
                self.assertEqual(br.platform_font_family({"familyName": family, "postScriptName": "PingFangSC-Semibold"}), family)

    def test_existing_canonical_family_is_not_rewritten(self):
        self.assertEqual(br.platform_font_family({"familyName": "PingFang SC", "postScriptName": "PingFangSC-Regular"}), "PingFang SC")

    def test_report_preserves_browser_family_and_postscript_evidence(self):
        class SyntheticChrome:
            def call(self, method, params=None):
                if method == "DOM.getDocument":
                    return {"root": {"nodeId": 1}}
                if method == "DOM.querySelectorAll":
                    return {"nodeIds": [2]}
                if method == "CSS.getPlatformFontsForNode":
                    return {"fonts": [{"familyName": "蘋方-簡", "postScriptName": "PingFangSC-Semibold", "glyphCount": 3}]}
                return {}

            def evaluate(self, *args, **kwargs):
                return [["SYNTHETIC", "合成样例"]]

        result = br.Chrome.fonts_used(SyntheticChrome())
        self.assertTrue(result)
        for entry in result:
            font = entry["fonts"][0]
            self.assertEqual(font["family"], "PingFang SC")
            self.assertEqual(font["reported_family"], "蘋方-簡")
            self.assertEqual(font["postscript"], "PingFangSC-Semibold")
            self.assertEqual(font["glyphs"], 3)


if __name__ == "__main__":
    unittest.main()
