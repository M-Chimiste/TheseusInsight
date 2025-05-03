from arxiv_harvester import ArxivOAHarvester
from datetime import datetime, timedelta
import pandas as pd


class ArxivDataProcessor:
    """
    A class to process and download data from the arXiv repository.

    This class is designed to facilitate the retrieval and processing of data from the arXiv repository. It allows for the specification of a date range, category, and subcategories to filter the data. The data is then downloaded and processed into a pandas DataFrame for further analysis.

    Attributes:
        start_date (str): The start date of the date range for data retrieval.
        end_date (str): The end date of the date range for data retrieval.
        category (str): The category of papers to retrieve.
        subcategories (list[str]): A list of subcategories to filter the papers by.
        num_days (int): The number of days before the current date to set as the end date if not specified.
        max_results (int): The maximum number of results to retrieve.

    Methods:
        download_and_process_data(start_date=None, end_date=None): Downloads and processes data from arXiv based on the specified parameters.
    """
    def __init__(self,
                start_date: str|None = None,
                end_date: str|None = None,
                category: str = "cs",
                subcategories: list[str] = ["cs.ai", "cs.lg", "cs.cl", "cs.ir", "cs.ma", "cs.cv"],
                num_days: int|None = 7,
                max_results: int|None = None
                ):
        
        if not end_date:
            self.end_date = (datetime.now() - timedelta(days=num_days)).strftime("%Y-%m-%d")
        else:
            self.end_date = end_date
            
        if not start_date:
            self.start_date = datetime.now().strftime("%Y-%m-%d")
        else:
            self.start_date = start_date
            
        self.category = category
        self.subcategories = subcategories
        self.num_days = num_days
        self.max_results = max_results

        
    def download_and_process_data(self, start_date=None, end_date=None):
        """
        Downloads and processes data from arXiv based on the specified parameters.

        Args:
            start_date (str): The start date of the date range for data retrieval.
            end_date (str): The end date of the date range for data retrieval.
        """
        start_date = start_date or self.start_date
        end_date = end_date or self.end_date
        
        if not start_date:
            raise ValueError("Start date is required")
        if not end_date:
            raise ValueError("End date is required")
        
        harvester = ArxivOAHarvester(
            category=self.category,
            subcategories=self.subcategories,
            date_from=end_date,
            date_until=start_date,
            max_results=self.max_results
        )
        _ = harvester.harvest()
        data_df = harvester.to_dataframe()
        data_df['date'] = pd.to_datetime(data_df['created'])
        return data_df
            
            
        
        
