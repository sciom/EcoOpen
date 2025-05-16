# Keywords for EcoOpen package to identify data and code availability statements

keywords = {
    "data_availability": [
        "Data Availability",
        "Availability of Data",
        "Data Access",
        "Supporting Information",
        "Supplementary Information",
    ],
    "data": [
        "data",
        "dataset",
        "datasets",
        "raw data",
        "processed data",
        "supporting data",
        "supplementary data",
    ],
    "all_data": [
        "all data",
        "complete data",
        "full data",
        "entire dataset",
    ],
    "dataset_name": [
        "database",
        "repository",
        "archive",
    ],
    "available": [
        "available",
        "accessible",
        "provided",
        "shared",
        "deposited",
        "publicly available",
        "freely available",
    ],
    "was_available": [
        "was available",
        "were available",
        "made available",
        "has been made available",
        "have been made available",
    ],
    "not_available": [
        "not available",
        "unavailable",
        "not shared",
        "not provided",
        "not accessible",
        "not deposited",
    ],
    "not_data": [
        "no data",
        "no dataset",
        "no datasets",
        "no raw data",
        "no processed data",
    ],
    "repositories": [
        "Dryad",
        "Zenodo",
        "Figshare",
        "Dataverse",
        "Mendeley Data",
        "OSF",
        "Open Science Framework",
    ],
    "field_specific_repo": [
        "GenBank",
        "SRA",
        "Sequence Read Archive",
        "GEO",
        "Gene Expression Omnibus",
        "ArrayExpress",
        "ENA",
        "European Nucleotide Archive",
    ],
    "github": [
        "GitHub",
        "gitlab",
        "bitbucket",
    ],
    "upon_request": [
        "upon request",
        "on request",
        "by request",
        "available upon reasonable request",
        "available on reasonable request",
    ],
    "supplement": [
        "supplementary material",
        "supplemental material",
        "supporting material",
        "supplementary information",
        "supplemental information",
        "supporting information",
        "supplementary data",
        "supplemental data",
        "supporting data",
        "supplementary files",
        "supplemental files",
        "supporting files",
    ],
    "supplemental_table_name": [
        "Table S[0-9]+",
        "Figure S[0-9]+",
        "Appendix S[0-9]+",
        "Suppl Table [0-9]+",
        "Suppl Fig [0-9]+",
        "Supplementary Table [0-9]+",
        "Supplementary Figure [0-9]+",
    ],
    "supplemental_dataset": [
        "Dataset S[0-9]+",
        "Suppl Dataset [0-9]+",
        "Supplementary Dataset [0-9]+",
    ],
    "source_code": [
        "source code",
        "software",
        "code",
        "scripts",
        "program",
        "algorithm",
    ],
    "accession_nr": [
        r"[A-Z][0-9]{6,8}",           # GenBank/EMBL/DDBJ (e.g., AF123456)
        r"SRR[0-9]{6,}",              # SRA (Sequence Read Archive, e.g., SRR123456)
        r"PRJ(NA|EB|DB)[0-9]{6,}",    # BioProject (e.g., PRJNA123456)
        r"[A-Z]{2}[0-9]{6}",          # Another format (e.g., AB123456)
        r"[A-Z]{1,2}_[0-9]{5,8}",     # Format with underscore (e.g., NC_123456)
        r"[A-Z]{3}[0-9]{5,}",         # Another format (e.g., GEO12345)
    ],
    "code_availability": [
        "Code Availability",
        "Software Availability",
        "Availability of Code",
        "Supporting Information",
    ],
}