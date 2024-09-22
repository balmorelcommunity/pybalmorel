from dataclasses import dataclass, field
from urllib.parse import urljoin
import pandas as pd
import os
import requests

@dataclass
class TechData:
    files: dict = field(default_factory=lambda: {
        "el_and_dh" :   "technology_data_for_el_and_dh.xlsx",
        "indi_heat" :   "technology_data_heating_installations.xlsx",
        "ren_fuels" :   "data_sheets_for_renewable_fuels.xlsx",
        "storage"   :   "technology_datasheet_for_energy_storage.xlsx",
        "ccts"      :   "technology_data_for_carbon_capture_transport_storage.xlsx",
        "indu_heat" :   "technology_data_for_industrial_process_heat_0.xlsx",
        "trans"     :   "energy_transport_datasheet.xlsx"                              
    })
    path: str = r"C:\Users\mathi\gitRepos\balmorel-preprocessing\RawDataProcessing\Data\Technology Data" # Change this later
    
    def load(self, file: str):
        f = pd.read_excel(os.path.join(self.path, self.files[file]),
                          sheet_name='alldata_flat')
        return f

    # Function to download a file from a URL and save it to a specified folder
    def download_file(self, url, save_folder, filename=None):
        """
        Downloads a file from a given URL and saves it to a specified folder.
        Args:
            url (str): The URL of the file to download.
            save_folder (str): The folder where the file should be saved.
            filename (str, optional): The name to save the file as. If not provided, the filename is extracted from the URL.
        Returns:
            str: The full path to the saved file.
        Raises:
            requests.exceptions.RequestException: If the download fails.
        Notes:
            - The function ensures that the save folder exists.
            - The file is downloaded in chunks to handle large files efficiently.
        chunk_size:
            The size of each chunk of data to be written to the file. In this case, it is set to 8192 bytes (8 KB).
        """
        # Make sure the save folder exists
        os.makedirs(save_folder, exist_ok=True)

        # If no filename is provided, extract the filename from the URL
        if filename is None:
            filename = url.split("/")[-1]
        
        # Full path to save the file
        save_path = os.path.join(save_folder, filename)

        # Download the file with streaming to handle large files
        with requests.get(url, stream=True) as response:
            response.raise_for_status()  # Raise an error if the download fails
            with open(save_path, 'wb') as file:
                for chunk in response.iter_content(chunk_size=8192):
                    file.write(chunk)
        
        print(f"Downloaded file to: {save_path}")
        return save_path

    def download_catalogue(self, 
                           file: str,
                           save_to_folder: str = '.',
                           domain: str = "https://ens.dk/sites/ens.dk/files/Analyser/"):
        """Downloads technology catalogue from DEA website

        Args:
            file (str): _description_
            save_to_folder (str, optional): _description_. Defaults to '.'.
            domain (_type_, optional): _description_. Defaults to "https://ens.dk/sites/ens.dk/files/Analyser/".
        """
        try:
            # You probably used the short name used in this class
            filename = self.files[file]
        except KeyError:
            # ..in case you wrote the full name of the file
            filename = file
            
        if not(filename in os.listdir(save_to_folder)):
            self.download_file(urljoin(domain, filename), save_to_folder)
        else:
            print('\nThe file:\t\t%s\nalready exists in:\t%s'%(self.files[file], save_to_folder))

    def download_all_catalogues(self,
                                save_to_folder: str = '.'):
        for file in self.files.keys():
            self.download_catalogue(file, save_to_folder)
        
if __name__ == '__main__':
    td = TechData()
    
    # Download catalogues
    # td.download_catalogue("el_and_dh")
    # td.download_all_catalogues()
    
    # Get electricity and district heating examples
    f = td.load('el_and_dh')
    # series = pd.Series(f.par.unique())
    # print(series[series.str.find('Nominal investment (*total)') != -1])
    year = 2050
    tech = 'Offshore wind turbines - renewable power - wind - large'
    estimate = 'ctrl' # ctrl, lower, upper
    print(f.query("Technology == @tech and cat == 'Financial data' and year == @year and est == @estimate"))