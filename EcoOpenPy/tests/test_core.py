import unittest
from ecoopen import clean_text, truncate_statement, validate_doi, extract_urls_from_text, score_data_statement

class TestEcoOpenCore(unittest.TestCase):
    def test_clean_text_removes_invisible(self):
        text = "Hello\u200bWorld\u202c!"
        cleaned = clean_text(text)
        self.assertNotIn("\u200b", cleaned)
        self.assertNotIn("\u202c", cleaned)
        self.assertEqual(cleaned, "HelloWorld!")

    def test_truncate_statement(self):
        s = "a" * 600
        truncated = truncate_statement(s, max_length=100)
        self.assertTrue(truncated.endswith("..."))
        self.assertEqual(len(truncated), 100)

    def test_validate_doi(self):
        self.assertTrue(validate_doi("10.1000/xyz123"))
        self.assertFalse(validate_doi("not_a_doi"))

    def test_extract_urls_from_text(self):
        text = "Data at https://zenodo.org/record/12345 and code at https://github.com/user/repo."
        urls = extract_urls_from_text(text)
        self.assertIn("https://zenodo.org/record/12345", urls)
        self.assertIn("https://github.com/user/repo", urls)

    def test_score_data_statement(self):
        s = "All data are available in Zenodo."
        score = score_data_statement(s, "Available in Repository")
        self.assertTrue(score > 0)

if __name__ == "__main__":
    unittest.main()
