# Detect and download open data in ecological publications \- EcoOpen data detection tool (EoDd)

Domagoj Hackenberger Kutuzović​1,

Tamara Đerđ​1,

Branimir Hackenberger Kutuzović​1

Anita Tarandek​2

Antica Čulina​2,\*

1 Sciom d.o.o., Osijek, Croatia    
2 Ruđer Bošković Institute, Zagreb, Croatia    
\* Corresponding author: *aculina@irb.hr*    
 These authors contributed equally to this work.

# Abstract

Sharing open research data alongside publications is becoming increasingly common in ecology and evolutionary biology, with data commonly shared in supplements or repositories. Despite this progress, the use of open research data still needs to be improved. This is partly caused by the difficulty of detecting data sharing manually, especially because data sharing is often inconsistently reported. Second, data access and download often require significant effort. The same reasons make it difficult to assess trends in data-sharing rates and best practices in data-sharing. These are of interest to institutions, funders, and publishers who may wish to automate the assessment of open data policy success.

In this study, we extend an existing algorithm originally developed to detect data sharing in biomedical literature and adapt it for ecological and evolutionary research applications. The EcoOpen Data Detection tool performs three key tasks: (a) identify instances of data and material sharing in ecology and evolutionary biology publications, (b) extract details about data-sharing practices, such as repository locations and data formats, and (c) automate the download of shared datasets.

The EcoOpen Data Detection tool is fully open-source and can support diverse applications. Researchers can use it to collect datasets for reuse, including re-analyses and meta-analyses. Institutions, journals, and funding agencies can use it to monitor open data practices and ensure compliance with data-sharing policies. This tool thus provides a valuable resource for advancing transparency, reproducibility, and data accessibility in the field. The EoDd is available at [https://github.com/sciom/EcoOpen](https://github.com/sciom/EcoOpen)

# Introduction

Research data are fundamental to ecological and evolutionary research, serving as the foundation for scientific discovery and knowledge building (Reichman, Jones, and Schildhauer 2011; Michener 2015; Culina, Baglioni, et al. 2018). These data have immense potential for reuse by other researchers and stakeholders, particularly in enabling evidence synthesis to detect global trends, patterns, and processes (Culina, Crowther, et al. 2018)). Furthermore, open data associated with published papers support reproducibility, a cornerstone of scientific integrity that builds trust in the validity of original results (Powers and Hampton 2019). In recognition of these benefits, many ecology and evolution journals and funding agencies have adopted open data policies (Berberi and Roche 2022; Roche et al. 2022). However, compliance with these policies is rarely checked or enforced (Berberi and Roche 2022; Roche et al. 2022). Monitoring compliance on a large scale is challenging due to the sheer volume of published articles.

Despite the growing availability of open data, its use remains relatively low among researchers for two primary reasons. First, locating data associated with published papers is not straightforward, as statements on data-sharing are often inconsistently reported or buried within the main text. Second, the quality of shared data frequently fails to meet standards such as the FAIR principles (Findable, Accessible, Interoperable, and Reusable; Wilkinson et al. (2016)), making it difficult to reuse effectively.

To maximize the utility of open data, published articles should ideally include explicit data availability statements that indicate where the data are stored and provide direct links or references to the data. Best practices further recommend that data are deposited in trusted repositories, which may be discipline-specific (e.g., “GBIF”: https://www.gbif.org/what-is-gbif) or general-purpose (e.g., “Dryad” (2024): https://datadryad.org). Data should also be deposited in a machine-readable format, accompanied by rich meta-data. However, this ideal scenario is rarely realized. Even when data are shared, mentions of data sharing may be scattered within the main text, making them difficult to detect, or not even present. Data are often shared as supplementary materials rather than through repositories, and such materials rarely explicitly identify their contents as research data. Even when supplementary materials contain data, these are frequently provided in suboptimal formats, such as PDF tables, rather than machine-readable formats like CSV files.

To address these challenges, we have developed the **EcoOpen Data Detection Tool (EoDd)**, an automated solution designed to: (1) detect instances of data sharing in published articles, (2) download available data, (3) extract data and code availability statements, (4) identify the formats of shared data, and (5) determine the locations where data have been deposited.

The EcoOpen Data Tool builds on the existing algorithm `OddPub`, which was originally developed to detect data sharing in biomedical literature (Riedel, Kip, and Bobrov 2020). However, the EoDd tool introduces several key elements tailored to the needs of ecology and evolutionary biology. It is also optimized for faster PDF processing, incorporates web mining capabilities, and allows users to search for papers, retrieve available PDFs, and download open data directly. By streamlining these processes, the EoDd tool facilitates the reuse of research data and supports large-scale monitoring of data-sharing practices and compliance with best practices.

# Methods

## Definition of Open Research Data

EoDd is designed to detect open research data shared in association with published articles. Research data include any datasets used to conduct analyses or generate plots reported in an article. These data may be raw or processed but are not fully analyzed. For instance, raw data could include records of marked individuals observed in a wild population over specific periods, such as sightings recorded with dates and times. Processed data might summarize these observations, such as survival analysis datasets indicating whether individuals were observed (1) or not observed (0) in a given year. Research data may also be primary (collected directly through experiments or fieldwork) or secondary (compiled from existing studies, as in meta-analyses).

For data to qualify as open research data, they must be accessible to everyone without restrictions. While open data ideally adhere to the FAIR principles (Findable, Accessible, Interoperable, and Reusable; Wilkinson et al. (2016)), this is likely rarely the case in ecology (Roche et al. 2015). EoDd tool focuses on detecting data that meet the following criteria:

1. **Explicit mention of data sharing**: The article explicitly states that data have been shared (e.g., “data were shared,” “data are accessible”) and provides a clear identifier such as a DOI, URL, database ID, or reference to supplementary materials.

2. **Freely accessible**: The data are freely available for access and download, excluding datasets that require requests or registration for access.

3. **Relevant to the article**: The shared data were used for at least some of the analyses or plots reported in the article. The tool does not verify the reusability of these data.

4. **In machine-readable format**: The data are either provided in a machine-readable format (e.g., CSV) or can be easily converted into such a format.

## Package Development

EcoOpen data detection tool was inspired by the OddPub R package (Riedel, Kip, and Bobrov 2020), which uses text-mining algorithms to detect and flag data-sharing practices in biomedical literature. While both tools share similar principles, EoDd is specifically tailored to the needs of ecology and evolutionary biology, and it further introduces several enhancements. These include faster PDF processing, web-mining capabilities, and the ability to search, retrieve, and download both articles and associated open data.

The EoDd workflow consists of five key steps:

1. **Article search**: Identify relevant articles using OpenAlex or CrossRef APIs.

2. **Article download**: Retrieve full-text articles when available.

3. **Data detection**: Analyze the text for mentions of data sharing.

4. **Data download**: Automatically download accessible datasets.

5. **Extraction**: Extract data availability statements and details about shared data.

The data tool is open-source and requires only basic Python experience. Plans include R-based wrap for wider accessibility and GUI based interface for a user-friendly experience.

### Paper Search

EoDd performs queries for scientific articles using the OpenAlex database primarily (“OpenAlex: The Open Catalog to the Global Research System” 2024), which provides metadata for millions of publications. Searches can be conducted based on keywords, authors, or DOIs, offering flexibility in locating relevant papers. The tool also supports integration with the CrossRef database to extend its coverage. The user can specify the maximum number of articles to retrieve, sorting options, and other search parameters. To ensure the legality of article downloads, EoDd prioritizes open-access repositories and publisher websites. Articles behind paywalls are flagged for manual review or alternative retrieval methods.

OpenAlex API (“Overview | OpenAlex Technical Documentation” 2024\) was chosen for its extensive coverage of scientific literature with a focus on open-access articles. The API allows for flexible search queries and provides metadata essential for identifying relevant articles. CrossRef was selected as a secondary source to complement OpenAlex and expand the search scope. The combination of these two databases ensures comprehensive coverage of scientific literature.

### Paper Download

EoDd streamlines the automated retrieval of full-text articles by searching open-access repositories, publisher websites, and other legitimate sources. If access is restricted—such as by paywalls or CAPTCHAs—the tool flags these articles for manual review or alternative retrieval methods.

Using DOIs, EoDd locates articles through targeted searches on publisher sites and open-access platforms. While it employs simulated browsing behavior to navigate common access barriers, certain articles may remain inaccessible due to advanced security measures. In such cases, EoDd highlights these items for further user intervention.

Additionally, EoDd supports the analysis of manually downloaded PDF files, which is useful to users who already have access to articles through institutional subscriptions or other sources. This feature is particularly advantageous for researchers who can obtain articles independently and wish to integrate them into EcoOpen’s workflow.

### Data Detection

EcoOpen employs text mining to detect mentions of data sharing within articles. Similar to OddPub, the algorithms search for specific phrases and keywords indicating data availability, data sharing, or data repositories. This involves parsing sectioned article text to identify data-sharing statements and exclude irrelevant text, such as acknowledgments or references to data that are shared. The algorithm also identifies references to common data repositories like Dryad, Zenodo, and Figshare and extracts dataset-specific identifiers, including DOIs and URLs of importance for data retrieval.

### Data Download

When data-sharing references are identified, EcoOpen attempts to retrieve the datasets directly from the detected sources. This process adheres to repository terms of use and logs unsuccessful attempts for user review. During data retrieval, the tool verifies that the data are accessible and in machine-readable formats. If the data are not directly downloadable (e.g., require registration), the tool flags them for manual review or alternative retrieval methods. Also, the tool logs the data download status for each article, including successful downloads, failed attempts, and inaccessible data. With data download, the tool also notes metadata about the data, such as the format in which data is stored and the database where it is stored ((tbl:metadata)).

*Metadata extracted by EcoOpen {\#tbl:metadata}*

| Metadata | Description |
| :---- | :---- |
| DOI | Digital Object Identifier of the dataset |
| Article title | Title of the article |
| Authors | Authors of the article |
| Published | Date of publication |
| URL | URL of the dataset |
| Journal | Journal where the article was published |
| Has fulltext | Availability of the full text |
| Is OA | Open access status |
| Paper download status | Status of the paper download |
| Path | Path to the downloaded paper |
| Format | Format of the dataset (e.g., CSV, XLSX, PDF) |
| Repository | Name of the repository where the dataset is stored |
| Repository URL | URL of the repository where the dataset is stored |
| Download status | Status of the dataset download (e.g., successful, failed) |
| Download date | Date when the dataset was downloaded |
| Download path | Path to the downloaded dataset |
| Data size | Size of the downloaded dataset |
| Data availability statement | Text extracted from the article indicating data availability |
| Code availability statement | Text extracted from the article indicating code availability |

### Full workflow

**import** EcoOpen.core **as** EcoOpen

papers \= EcoOpen.FindPapers(  
    doi\=\[  
        "10.7717/peerj.6150",  
        "10.7717/peerj.2951",  
        \],  
    number\_of\_papers\=20,  
    sort\="published"  
    )

papers\_download \= EcoOpen.DownloadPapers(  
    papers,  
    output\_dir\="\~/Documents/papers",  
    other\_sources\=True  
    )

data \= EcoOpen.FindOpenData(papers\_download, method\="web")  
data \= EcoOpen.FindOpenData(data, method \= "keywords")  
data\_download \= EcoOpen.DownloadData(  
    data, output\_dir\="\~/Documents/data")

# Validation

The performance of EeDd was validated by a manual inspection of 300 randomly selected articles from eligible journals. Two validators (AC, AT) have each extracted the relevant variables from these 300 articles and compared extractec values to the ones obtained by the algorithm. The matching was high (\>93% for any of the variables, range 93%-100%), thus no further adjustments were needed. 

# Discussion

The EoDd package is an open-source tool designed for a broad range of users, including researchers, research institutions, funders, and publishers. Its primary functionalities are centered around facilitating data collection and analysis while promoting compliance with open data policies. The package is user-friendly and accessible to anyone with basic Python experience, offering versatile applications across various domains.

Researchers, educators, conservationists, and other stakeholders interested in the use of open data related to ecology and evolutionary biology will be primarily interested in the application of the EoDD for the detection of relevant datasets for potential further use. This includes searching for scientific papers by keyword, author, or DOI, downloading papers, and searching for mentions of open data within these articles. Furthermore, researchers can extract and download open data, including data and code availability statements, and identify the formats in which data are stored and the repositories where the data are archived. These features enable researchers to reuse data on their own or within the evidence synthesis.

Institutions, funders, and journals can use EeDd to monitor trends in open data practices and evaluate compliance with open data policies. Based on these, they might want to devise solutions to for example increasing compliance with the policies. Although the tool does not differentiate between publication types (e.g., research articles versus reviews), users can focus on specific subsets of interest, such as articles from a particular journal or publisher.

While the tool helps detect the presence of shared data, users should independently assess the usability of the data, as the tool does not assess the compliance of the data with the FAIR principles. 

# Conclusion:

The EcoOpen Data Detection package is a versatile and accessible tool for promoting transparency and data re-use in ecological and evolutionary biology esearch. By supporting data reuse and monitoring, it fosters collaboration and adherence to open science principles in ecology and evolutionary biology.

References:

Berberi, Ilias, and Dominique G. Roche. 2022\. “No Evidence That Mandatory Open Data Policies Increase Error Correction.” *Nature Ecology & Evolution* 6 (11): 1630–33. [https://doi.org/10.1038/s41559-022-01879-9](https://doi.org/10.1038/s41559-022-01879-9).

Culina, Antica, Miriam Baglioni, Tom W. Crowther, Marcel E. Visser, Saskia Woutersen-Windhouwer, and Paolo Manghi. 2018\. “Navigating the Unfolding Open Data Landscape in Ecology and Evolution.” *Nature Ecology & Evolution* 2 (3): 420–26. [https://doi.org/10.1038/s41559-017-0458-2](https://doi.org/10.1038/s41559-017-0458-2).

Culina, Antica, Thomas W. Crowther, Jip J. C. Ramakers, Phillip Gienapp, and Marcel E. Visser. 2018\. “How to Do Meta-Analysis of Open Datasets.” *Nature Ecology & Evolution* 2 (7): 1053–56. [https://doi.org/10.1038/s41559-018-0579-2](https://doi.org/10.1038/s41559-018-0579-2).

“Dryad.” 2024\. 2024\. [https://datadryad.org/stash](https://datadryad.org/stash).

Gallagher, Rachael V., Daniel S. Falster, Brian S. Maitner, Roberto Salguero-Gómez, Vigdis Vandvik, William D. Pearse, Florian D. Schneider, et al. 2020\. “Open Science Principles for Accelerating Trait-Based Science Across the Tree of Life.” *Nature Ecology & Evolution* 4 (3): 294–303. [https://doi.org/10.1038/s41559-020-1109-6](https://doi.org/10.1038/s41559-020-1109-6).

“GBIF.” n.d. Accessed November 29, 2024\. [https://www.gbif.org/](https://www.gbif.org/).

Michener, William K. 2015\. “Ecological Data Sharing.” *Ecological Informatics* 29 (September): 33–44. [https://doi.org/10.1016/j.ecoinf.2015.06.010](https://doi.org/10.1016/j.ecoinf.2015.06.010).

“OpenAlex: The Open Catalog to the Global Research System.” 2024\. 2024\. [https://openalex.org/](https://openalex.org/).

“Overview | OpenAlex Technical Documentation.” 2024\. July 30, 2024\. [https://docs.openalex.org](https://docs.openalex.org).

Powers, Stephen M., and Stephanie E. Hampton. 2019\. “Open Science, Reproducibility, and Transparency in Ecology.” *Ecological Applications* 29 (1): e01822. [https://doi.org/10.1002/eap.1822](https://doi.org/10.1002/eap.1822).

Reichman, O. J., Matthew B. Jones, and Mark P. Schildhauer. 2011\. “Challenges and Opportunities of Open Data in Ecology.” *Science* 331 (6018): 703–5. [https://doi.org/10.1126/science.1197962](https://doi.org/10.1126/science.1197962).

Riedel, N., M. Kip, and E. Bobrov. 2020\. “Oddpub – a Text-Mining Algorithm to Detect Data Sharing in Biomedical Publications.” *Data Science Journal* 19 (1): 42\. [https://doi.org/10.5334/dsj-2020-042](https://doi.org/10.5334/dsj-2020-042).

Roche, Dominique G., Ilias Berberi, Fares Dhane, Félix Lauzon, Sandrine Soeharjono, Roslyn Dakin, and Sandra A. Binning. 2022\. “Slow Improvement to the Archiving Quality of Open Datasets Shared by Researchers in Ecology and Evolution.” *Proceedings of the Royal Society B: Biological Sciences* 289 (1975): 20212780\. [https://doi.org/10.1098/rspb.2021.2780](https://doi.org/10.1098/rspb.2021.2780).

Roche, Dominique G., Loeske E. B. Kruuk, Robert Lanfear, and Sandra A. Binning. 2015\. “Public Data Archiving in Ecology and Evolution: How Well Are We Doing?” *PLOS Biology* 13 (11): e1002295. [https://doi.org/10.1371/journal.pbio.1002295](https://doi.org/10.1371/journal.pbio.1002295).

Wilkinson, Mark D., Michel Dumontier, IJsbrand Jan Aalbersberg, Gabrielle Appleton, Myles Axton, Arie Baak, Niklas Blomberg, et al. 2016\. “The FAIR Guiding Principles for Scientific Data Management and Stewardship.” *Scientific Data* 3 (1): 160018\. [https://doi.org/10.1038/sdata.2016.18](https://doi.org/10.1038/sdata.2016.18).