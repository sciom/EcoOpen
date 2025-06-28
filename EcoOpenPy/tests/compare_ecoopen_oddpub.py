import pandas as pd

# Load results
ecoopen = pd.read_csv("../ecoopen_output_from_pdfs.csv")
oddpub = pd.read_csv("../oddpub_output_from_pdfs.csv")

# Merge on filename (adjust column names if needed)
merged = pd.merge(
    ecoopen, oddpub, left_on="pdf_file", right_on="pdf_file", how="outer", suffixes=("_ecoopen", "_oddpub")
)

# Simple comparison: did both find a statement?
merged["ecoopen_found"] = merged["extraction"].notnull() & (merged["extraction"] != "None")
merged["oddpub_found"] = merged["oddpub_found"] == True
merged["both_found"] = merged["ecoopen_found"] & merged["oddpub_found"]
merged["ecoopen_only"] = merged["ecoopen_found"] & (~merged["oddpub_found"])
merged["oddpub_only"] = (~merged["ecoopen_found"]) & merged["oddpub_found"]

# Print summary
print("Total PDFs:", len(merged))
print("Both found:", merged["both_found"].sum())
print("EcoOpen only:", merged["ecoopen_only"].sum())
print("Oddpub only:", merged["oddpub_only"].sum())

# Save detailed comparison
merged.to_csv("ecoopen_vs_oddpub_comparison.csv", index=False)
print("Detailed comparison saved to ecoopen_vs_oddpub_comparison.csv")
