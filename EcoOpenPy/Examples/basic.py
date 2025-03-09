from EcoOpen.core import FindPapers, DownloadPapers, FindOpenData, DownloadData


papers = FindPapers(
    author="Antica Čulina"
)

papers = DownloadPapers(papers, "~/ecoopentest")

data = FindOpenData(papers, method="keywords")