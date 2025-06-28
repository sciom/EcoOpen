import unittest
from ecoopen import extract_all_information

class TestExtractAllInformation(unittest.TestCase):
    def test_extract_all_information_basic(self):
        text = """
        Data Availability: All data are available at https://zenodo.org/record/12345. 
        Code Availability: Code is on https://github.com/user/repo. 
        The accession number is PRJNA123456. 
        DOI: 10.1000/xyz123
        """
        result = extract_all_information(text)
        self.assertIn("https://zenodo.org/record/12345", result["data_urls"])
        self.assertIn("https://github.com/user/repo", result["code_urls"])
        self.assertIn("10.1000/xyz123", result["dois"])
        self.assertIn("PRJNA123456", result["accessions"])
        self.assertIn("All data are available at https://zenodo.org/record/12345.", result["data_statements"])
        self.assertIn("Code is on https://github.com/user/repo.", result["code_statements"])

if __name__ == "__main__":
    unittest.main()
