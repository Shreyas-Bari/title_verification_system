import importlib
import os
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory


class DummyVerifier:
    def __init__(self, titles=None):
        self.titles = titles or ["Hindustan"]
        self.titles_lower_set = {title.lower() for title in self.titles}


class AdminRuleTests(unittest.TestCase):
    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.config_path = Path(self.tmp.name) / "rules_config.json"
        os.environ["PRGI_RULES_CONFIG_PATH"] = str(self.config_path)

        import rule_store
        import matcher

        self.rule_store = importlib.reload(rule_store)
        self.matcher = importlib.reload(matcher)
        self.rule_store.reset_to_defaults()

    def tearDown(self):
        os.environ.pop("PRGI_RULES_CONFIG_PATH", None)
        self.tmp.cleanup()

    def _verifier(self, titles=None):
        verifier = DummyVerifier(titles)
        verifier._check_disallowed_words = self.matcher.TitleVerifier._check_disallowed_words.__get__(
            verifier, DummyVerifier
        )
        verifier._check_title_combination = lambda candidate: []
        verifier._check_affix_collision = self.matcher.TitleVerifier._check_affix_collision.__get__(
            verifier, DummyVerifier
        )
        verifier._compute_lexical_scores = lambda candidate: []
        verifier._compute_semantic_scores = lambda candidate, match_results: match_results
        verifier._compute_combined_scores = lambda candidate, match_results: match_results
        verifier.verify = self.matcher.TitleVerifier.verify.__get__(verifier, DummyVerifier)
        return verifier

    def test_add_rule_rejects_matching_title(self):
        self.assertTrue(self.rule_store.add_disallowed_word("classified", "Custom"))
        result = self._verifier().verify("Classified Gazette")
        self.assertFalse(result.is_approved)
        self.assertTrue(any("classified" in issue for issue in result.issues))

    def test_remove_rule_stops_rejecting_because_of_that_rule(self):
        self.assertTrue(self.rule_store.add_disallowed_word("classified", "Custom"))
        self.assertTrue(self.rule_store.remove_disallowed_word("classified"))
        result = self._verifier().verify("Classified Gazette")
        self.assertTrue(result.is_approved)
        self.assertFalse(any("classified" in issue for issue in result.issues))

    def test_default_rules_include_core_statutory_terms(self):
        self.assertTrue(self.rule_store.reset_to_defaults())
        words = self.rule_store.get_disallowed_words()
        self.assertIn("police", words)
        self.assertIn("army", words)
        self.assertIn("cbi", words)

    def test_duplicate_word_does_not_create_duplicate_entries(self):
        self.assertTrue(self.rule_store.add_disallowed_word("classified", "Custom"))
        self.assertFalse(self.rule_store.add_disallowed_word(" Classified ", "Custom"))
        entries = [
            item for item in self.rule_store.get_disallowed_words_detailed()
            if item["word"] == "classified"
        ]
        self.assertEqual(1, len(entries))

    def test_rules_persist_after_module_reload(self):
        self.assertTrue(self.rule_store.add_disallowed_word("temporary-rule", "Custom"))
        reloaded = importlib.reload(self.rule_store)
        self.assertIn("temporary-rule", reloaded.get_disallowed_words())

    def test_added_prefix_is_used_by_affix_matcher(self):
        self.assertTrue(self.rule_store.add_prefix("rashtriya"))
        issues = self._verifier(["Hindustan"])._check_affix_collision("Rashtriya Hindustan")
        self.assertTrue(issues)

    def test_added_suffix_is_used_by_affix_matcher(self):
        self.assertTrue(self.rule_store.add_suffix("samachar"))
        issues = self._verifier(["Hindustan"])._check_affix_collision("Hindustan Samachar")
        self.assertTrue(issues)

    def test_reset_removes_custom_rules_and_keeps_defaults(self):
        self.assertTrue(self.rule_store.add_disallowed_word("custom-only", "Custom"))
        self.assertTrue(self.rule_store.reset_to_defaults())
        words = self.rule_store.get_disallowed_words()
        self.assertNotIn("custom-only", words)
        self.assertIn("police", words)
        self.assertIn("army", words)
        self.assertIn("cbi", words)


if __name__ == "__main__":
    unittest.main()
