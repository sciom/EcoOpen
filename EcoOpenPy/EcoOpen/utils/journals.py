import pandas as pd
import os

cwd = os.getcwd()
cwd = cwd.replace(
    "/utils", ""
    )

journals = pd.read_csv(
    cwd+"/data/List_ecoevo_journals_latest.csv", index_col=0)

ID = journals.index.values
Journal = journals["Journal query"].values

data = list(Journal)
data = [i.replace("&", "") for i in data]
data = [i.replace(" and ", " ") for i in data]

journals = pd.DataFrame(columns=["Journal"], data=data)
journals.sort_values(by="Journal", inplace=True, ignore_index=True)
journals = journals["Journal"]
