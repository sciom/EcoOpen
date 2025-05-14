import logging
from ecoopen import process_and_analyze_dois

# Initialize logging for main process
logging.basicConfig(
    filename="ecoopen.log",
    level=logging.DEBUG,
    format="%(asctime)s - %(levelname)s - %(message)s",
    filemode='a'  # Append to log file
)

# Reduced DOI list for debugging; uncomment the full list for complete testing
dois = [
    "10.1046/j.1526-100x.2000.80038.x",
    "10.1006/jhev.1999.0361",
    "10.1023/A:1007643800508",
    "10.1016/S0022-0981(00)00211-2",
    "10.1007/PL00008879",
    "10.1046/j.1365-2664.2000.00543.x",
    "10.1111/j.1095-8312.2000.tb00208.x",
    "10.3354/meps206033",
    "10.1023/A:1005453220792",
    "10.1046/j.1365-2656.2000.00374.x",
    "10.1006/clad.1999.0127",
    "10.1016/S0022-0981(00)00208-2",
    "10.1098/rspb.2001.1642",
    "10.1016/S0304-3800(01)00257-5",
    "10.1080/002229301300323875",
    "10.1006/bijl.2001.0522",
    "10.1046/j.1365-294X.2001.01179.x",
    "10.2307/268022 QuickTime",
    "10.1007/S00265-001-0433-3",
    "10.1078/0367-2530-00055",
    "10.1023/A:1020951514763",
    "10.1016/j.ecoinf.2022.101808",
    "10.1016/j.ecoinf.2023.102204",
    "10.1016/S1055-7903(03)00161-1",
    "10.3390/d14080591",
    "10.1016/j.pedobi.2022.150843",
    "10.1186/s13717-021-00300-w",
    "10.1111/aje.13028",
    "10.1002/eco.2288",
    "10.1007/s00265-020-02952-8",
]



logging.info(f"Starting test with {len(dois)} DOIs")

df = process_and_analyze_dois(
    dois=dois,
    save_to_disk=True,
    email="your_real_email@domain.com",  # Replace with a valid Unpaywall-registered email
    download_dir="./pdf_downloads",
    data_download_dir="./data_downloads",
    target_formats=["csv", "xlsx"]
)

logging.info("Test completed")
print("Test completed. Output saved to ecoopen_output.csv")
print(df[["identifier", "doi", "title", "data_availability_statements", "downloaded_data_files"]])