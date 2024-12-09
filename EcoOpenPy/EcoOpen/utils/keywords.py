

available = [
    "included",
    "deposited",
    "released",
    "is provided",
    "are provided",
    "contained in",
    "available",
    "reproduce",
    "accessible",
    "can be accessed",
    "submitted",
    "can be downloaded",
    "reported in",
    "uploaded",
    "are public on"
    "provided"
    "archived"
]

was_available = [
    "was provided",
    "were provided",
    "was contained in",
    "were contained in",
    "was available",
    "were available",
    "was accessible",
    "were accessible",
    "deposited by",
    "were reproduced"
]

not_available = [
    "not included",
    "not deposited",
    "not released",
    "not provided",
    "not contained in",
    "not available",
    "not accessible",
    "not submitted"
]

field_specific_repo = [
    "GEO",
    "Deep Insight for Earth Science Data",
    "ESS-DIVE",
    "Gene Expression Omnibus",
    "European Nucleotide Archive",
    "National Center for Biotechnology Information",
    "European Molecular Biology Laboratory",
    "EMBL-EBI",
    "BioProject",
    "Sequence Read Archive",
    "SRA",
    "ENA",
    "MassIVE",
    "ProteomeXchange",
    "Proteome Exchange",
    "ProteomeExchange",
    "MetaboLights",
    "Array-Express",
    "ArrayExpress",
    "Array Express",
    "PRIDE",
    "DNA Data Bank of Japan",
    "DDBJ",
    "Genbank",
    "Protein Databank",
    "Protein Data Bank",
    "PDB",
    "Metagenomics Rapid Annotation using Subsystem Technology",
    "MG-RAST",
    "metabolights",
    "OpenAgrar",
    "Open Agrar",
    "Electron microscopy data bank",
    "emdb",
    "Cambridge Crystallographic Data Centre",
    "CCDC",
    "Treebase",
    "dbSNP",
    "dbGaP",
    "IntAct",
    "ClinVar",
    "European Variation Archive",
    "dbVar",
    "Mgnify",
    "NCBI Trace Archive",
    "NCBI Assembly",
    "UniProtKB",
    "Protein Circular Dichroism Data Bank",
    "PCDDB",
    "Worldwide Protein Data Bank",
    "wwPDB",
    "Structural Biology Data Grid",
    "NeuroMorpho",
    "G-Node",
    "Neuroimaging Informatics Tools and Resources Collaboratory",
    "NITRC",
    "EBRAINS",
    "GenomeRNAi",
    "Database of Interacting Proteins",
    "IntAct",
    "Japanese Genotype-phenotype Archive",
    "Biological General Repository for Interaction Datasets",
    "Genomic Expression Archive",
    "PeptideAtlas",
    "Environmental Data Initiative",
    "LTER Network Information System Data Portal",
    "Global Biodiversity Information Facility",
    "GBIF",
    "Integrated Taxonomic Information System",
    "ITIS",
    "Knowledge Network for Biocomplexity",
    "Morphobank",
    "The Network Data Exchange",
    "NDEx",
    "FlowRepository",
    "ImmPort",
    "Image Data Resource",
    "Eukaryotic Pathogen Database Resources",
    "EuPathDB",
    "Mouse Genome Informatics",
    "Rat Genome Database",
    "VectorBase",
    "Xenbase",
    "Zebrafish Model Organism Database",
    "ZFIN",
    "PhysioNet",
    "Research Domain Criteria Database",
    "RdoCdb",
    "Synapse",
    "UK Data Service",
    "caNanoLab",
    "ChEMBL",
    "STRENDA",
    "European Genome-phenome Archive",
    "European Genome phenome Archive",
    "Experimental Lakes Area",
    "IISD – ELA",
    "National Contaminants Information System",
    "NCIS",
    "Bedford Institute of Oceanography - Oceanographic Databases",
    "Institut océanographique de Bedford - Bases de données océanographiques",
    "Australian Urban Research Infrastructure Network",
    "AURIN",
    "Hakai Data",
    "Institute Data Systems",
    "Atlantic Canada Conservation Data Centre",
    "AC CDC",
    "Italian National Biodiversity Network",
    "Network Nazionale Biodiversità",
    "ForestPlots.net",
    "The Vegetation Plot Archive Project",
    "openLandscapes",
    "The Knowledge Collection for Landscape Science",
    "A vegetation data network for West Africa",
    "Canadian Environmental Sustainability Indicators",
    "CESI",
    "PPBio Data Repository",
    "Programa de Pesquisa em Biodiversidade Repositorio de Dados",
    "Environmental Information Data Centre",
    "EIDC",
    "National Biodiversity Information System of Mexico",
    "Sistema Nacional de Información sobre Biodiversidad de México",
    "Australian SuperSite Network Data Portal",
    "SupeSites Data Portal",
    "DEIMS-SDR",
    "Dynamic Ecological Information Management System",
    "Tree Atlas Project",
    "Marine Environmental Data Section",
    "Open Archive for Miscellaneous Data",
    "Biodiversity Exploratories Information System",
    "BExIS",
    "ICES data portal",
    "International Council for the Exploration of the Sea dataset collections",
    "Norwegian Marine Data Center",
    "Norsk marint datasenter",
    "Marine Microbial Database of India",
    "National Harvest Survey",
    "EarthWorks",
    "Environmental Data Initiative Repository",
    "EDI Data Portal",
    "The European Data Portal",
    "European data",
    "data.europa.eu",
    "Research Data Australia",
    "ARDC",
    "Santa Cruz Island Preserve Research Repository",
    "Dangermond Preserve Research Repository",
    "Draft Salmon Portal",
    "Arctic Data Portal",
    "NatCap",
    "California's Marine Protected Area Monitoring Program",
    "California MPA Monitoring Data Portal",
    "The Ocean Data Integration Initiative Testing Portal",
    "ODINI Testing Portal",
    "Ocean Biodiversity Information System",
    "OBIS",
    "accession number",
    "accession code",
    "accession numbers",
    "accession codes"
]

accession_nr = [
    "G(SE|SM|DS|PL)[[:digit:]]{2,}", #GEO
    "PRJ(E|D|N|EB|DB|NB)[:digit:]+",
    "SAM(E|D|N)[A-Z]?[:digit:]+",
    "[A-Z]{1}[:digit:]{4}", #GenBank
    "[A-Z]{2}[:digit:]{6}",
    "[A-Z]{3}[:digit:]{5}",
    "[A-Z]{4,6}[:digit:]{3,}",
    "GCA_[:digit:]{9}\\.[:digit:]+",
    "SR(P|R|X|S|Z)[[:digit:]]{3,}",
    "(E|P)-[A-Z]{4}-[:digit:]{1,}",
    "[:digit:]{1}[A-Z]{1}[[:alnum:]]{2}",
    "MTBLS[[:digit:]]{2,}",
    "10.17590",
    "10.5073",
    "10.25493",
    "10.6073",
    "10.15468",
    "10.5063",
    "[[:digit:]]{6}",
    "[A-Z]{2,3}_[:digit:]{5,}",
    "[A-Z]{2,3}-[:digit:]{4,}",
    "[A-Z]{2}[:digit:]{5}-[A-Z]{1}",
    "DIP:[:digit:]{3}",
    "FR-FCM-[[:alnum:]]{4}",
    "ICPSR [:digit:]{4}",
    "SN [:digit:]{4}"
]

repositories = [
    "figshare",
    "dryad",
    "zenodo",
    "dataverse",
    "DataverseNL",
    "osf",
    "open science framework",
    "mendeley data",
    "GIGADB",
    "GigaScience database",
    "OpenNeuro",
    "pangaea" # added by domagoj
]

github = ["github", "github.com", "github.io", "githubusercontent.com", "githubusercontent.io", "githubpages.com", "githubpages.io", "githubusercontent", "githubpages"]

data = [
    "data", 
    "dataset",
    "datasets"]

all_data = [
    "all data",
    "raw data",
    "full data set",
    "full dataset",
    "complete data set",
    "complete dataset",
]

not_data = [
    "not all data",
    "no raw data",
    "no full data set",
    "no complete data set",
    "no complete dataset",
    "no full dataset"
]

source_code = [
    "source code",
    "analysis script",
    "github",
    "SAS script",
    "SPSS script",
    "R script",
    "R code",
    "python script",
    "python code",
    "matlab script",
    "matlab code"
]

supplement = [
    "supporting information",
    "supplement",
    "supplementary information",
    "supplementary material",
    "supplementary data"
]

file_formats = [
    "csv",
    "zip",
    "xls",
    "xlsx",
    "sav",
    "cif",
    "fasta"
]

upon_request = [
    "upon request",
    "on request",
    "upon reasonable request"
]
data_availability = [
    "Data sharing",
    "Data Availability Statement",
    "Data Availability",
    "Data deposition",
    "Deposited Data",
    "Data Archiving",
    "Availability of data and materials",
    "Availability of data",
    "Data Accessibility",
    "Data Accessibility Statement",
    "Accessibility of data"]

supplemental_table_name = [
    "supplementary table",
    "supplementary tables",
    "supplemental table",
    "supplemental tables",
    "table", "tables",
    "additional file",
    "file",
    "files"
]

supplemental_dataset = [
    "supplementary data [[:digit:]]{1,2}",
    "supplementary dataset [[:digit:]]{1,2}",
    "supplementary data set [[:digit:]]{1,2}",
    "supplemental data [[:digit:]]{1,2}",
    "supplemental dataset [[:digit:]]{1,2}",
    "supplemental data set [[:digit:]]{1,2}"
]



# original scripd binds dataset_name to dataset_numbering
dataset_name = [
    "data", "dataset", "datasets", "data set", "data sets"
]

dataset_number = ["S[[:digit:]]{1,2}"]

# TODO: Check this!
data_journal_dois = [
    "10.1038/s41597-019-", "10.3390/data", "10.1016/j.dib"
]
    
keywords = {
    "available": available,
    "was_available": was_available,
    "not_available": not_available,
    "field_specific_repo": field_specific_repo,
    "accession_nr": accession_nr,
    "repositories": repositories,
    "github": github,
    "data": data,
    "all_data": all_data,
    "not_data": not_data,
    "source_code": source_code,
    "supplement": supplement,
    "file_formats": file_formats,
    "upon_request": upon_request,
    "data_availability": data_availability,
    "supplemental_table_name": supplemental_table_name,
    "supplemental_dataset": supplemental_dataset,
    "dataset_name": dataset_name,
    "dataset_number": dataset_number,
    "data_journal_dois": data_journal_dois
}