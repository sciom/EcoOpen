from EcoOpen.core import FindPapers, DownloadPapers, FindOpenData, DownloadData


papers = FindPapers(
    author="Antica Čulina"
)

papers = DownloadPapers(papers.loc[:], "~/ecoopentest")

data = FindOpenData(papers, method="keywords")

data = DownloadData(data, "~/ecoopentest_data")