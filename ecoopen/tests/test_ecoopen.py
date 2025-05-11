import unittest
from ecoopen import process_and_analyze_dois

class TestEcoOpen(unittest.TestCase):
    def test_process_and_analyze_dois(self):
        dois = ["10.3390/ecologies2030017"]
        df = process_and_analyze_dois(dois=dois, save_to_disk=False)
        self.assertEqual(len(df), 1)
        self.assertEqual(df["doi"].iloc[0], "10.3390/ecologies2030017")

if __name__ == "__main__":
    unittest.main()