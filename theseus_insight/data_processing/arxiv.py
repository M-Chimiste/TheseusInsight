from .unified_harvester import UnifiedArxivHarvester
from datetime import datetime, timedelta, date
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
                start_date: str | datetime | None = None,
                end_date: str | datetime | None = None,
                category: str = "cs",
                subcategories: list[str] = ["cs.ai", "cs.cl", "cs.lg", "cs.ir", "cs.ma", "cs.cv"],
                num_days: int|None = 7,
                max_results: int|None = None
                ):
        
        if not start_date:
            self.start_date = (datetime.now() - timedelta(days=num_days)).strftime("%Y-%m-%d")
        else:
            if isinstance(start_date, datetime):
                self.start_date = start_date.strftime("%Y-%m-%d")
            else:
                self.start_date = start_date
            
        if not end_date:
            self.end_date = datetime.now().strftime("%Y-%m-%d")
        else:
            if isinstance(end_date, datetime):
                self.end_date = end_date.strftime("%Y-%m-%d")
            else:
                self.end_date = end_date
            
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
        
        # --- Begin: Sanity check and swap if needed ---
        def to_datetime(dt):
            if isinstance(dt, datetime):
                return dt
            elif isinstance(dt, date):
                return datetime(dt.year, dt.month, dt.day)
            elif isinstance(dt, str):
                return datetime.strptime(dt, "%Y-%m-%d")
            else:
                raise TypeError(f"Unsupported date type: {type(dt)}")

        start_dt = to_datetime(start_date)
        end_dt = to_datetime(end_date)
        if start_dt > end_dt:
            print(f"Swapping start_date ({start_date}) and end_date ({end_date}) as start_date is after end_date.")
            start_dt, end_dt = end_dt, start_dt
        start_date = start_dt.strftime("%Y-%m-%d")
        end_date = end_dt.strftime("%Y-%m-%d")
        # --- End: Sanity check and swap if needed ---
        
        print(f"Start date: {start_date}, End date: {end_date}")
        print(f"Category: {self.category}, Subcategories: {self.subcategories}")

        with UnifiedArxivHarvester(
            category=self.category,
            subcategories=self.subcategories,
            date_from=start_date,
            date_until=end_date,
            max_results=self.max_results,
            verbose=True
        ) as harvester:
            records = harvester.harvest()
            data_df = harvester.to_dataframe()
            
            # Handle case where no records were retrieved
            if data_df.empty or len(records) == 0:
                print(f"No records found for date range {start_date} to {end_date}")
                print(f"Category: {self.category}, Subcategories: {self.subcategories}")
                
                # Create an empty DataFrame with the expected structure for downstream processing
                empty_df = pd.DataFrame(columns=[
                    'id', 'url', 'pdf_url', 'title', 'abstract', 'categories', 
                    'created', 'updated', 'doi', 'authors', 'affiliation'
                ])
                # Add the 'date' column that downstream code expects
                empty_df['date'] = pd.to_datetime([])
                return empty_df
            
            # Normal case: process the retrieved records
            data_df['date'] = pd.to_datetime(data_df['created'])
            return data_df
            
            
        
        
