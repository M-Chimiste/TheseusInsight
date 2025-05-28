import datetime
import gzip
import json
import os
import shutil

import pandas as pd
import requests


class PapersWithCode:

    def __init__(self, start_date=None, end_date=None):
        self.paper_dump_url = "https://production-media.paperswithcode.com/about/papers-with-abstracts.json.gz"  #This URL is static and updated daily per https://github.com/paperswithcode/paperswithcode-data
        # Surpisingly it's faster and easier to download a dump than query an API for the most current data.
        # Go figure... Please fix this paperswithcode...
        self.start_date = start_date
        self.end_date = end_date
        self.json_data = None

    def download_and_process_data(self, start_date=None, end_date=None):
        """Method to download and pre-process data for LLM consumption

        Args:
            start_date (str, optional): the string date for the time period selected (MM-DD-YYYY). Defaults to None.
            end_date (srr, optional): the string date for the time period selected (MM-DD-YYYY). Defaults to None.

        If both `start_date` and `end_date` are omitted, the method returns the entire dataset instead of raising an error.

        Raises:
            ValueError: Failure to provide a start_date
            ValueError: Failure to provide an end_date

        Returns:
            df: dataframe with the requisite queried data based on date.
        """

        # Resolve defaults
        if start_date is None:
            start_date = self.start_date
        if end_date is None:
            end_date = self.end_date

        # If both dates are still None, return the full dataset
        if start_date is None and end_date is None:
            json_data = self.json_data or self._fetch_data()
            self.json_data = json_data
            df = pd.DataFrame.from_dict(json_data)
            df['date'] = pd.to_datetime(df['date'])
            return df

        # If only one of the dates is provided, raise an explicit error
        if (start_date is None) != (end_date is None):
            raise ValueError("Both start_date and end_date must be provided together.")
        
        json_data = self.json_data
        
        if not json_data:
            json_data = self._fetch_data()
            self.json_data = json_data
        data_df = self._find_specific_date_data(start_date, end_date, json_data)
        return data_df
    

    def _fetch_data(self):
        """Method will download and extract the json data from papers with code

        Returns:
            list: List of dictionaries of the loaded data.
        """
        os.makedirs('temp_data', exist_ok=True)  # Generate a temp_data repository


        today = datetime.date.today()
        str_time = today.strftime("%Y-%m-%d")
        gzip_filename = f"temp_data/papers-with-code-{str_time}.json.gz"
        filename = f"temp_data/papers-with-code-{str_time}.json"
        
        with open(gzip_filename, "wb") as fb:
            response = requests.get(self.paper_dump_url)
            fb.write(response.content)

        with gzip.open(gzip_filename, "rb") as fr:
            with open(filename, "wb") as f_out:
                shutil.copyfileobj(fr, f_out)
        
        with open(filename, 'r') as f:
            json_data = json.load(f)
        
        return json_data


    def _find_specific_date_data(self, start_date, end_date, json_dict):
        """function to get specific data from the json data by a date range.
        Dates can be either a range or the same.

        Args:
            start_date (datetime): The desired start date.
            end_date (datetime): The desired end date.  Can be the same as start date.
            json_dict (list): List of dictionaries from the loaded papers with code data

        Returns:
            df: Pandas Dataframe of the associated data.
        """
        start_date = pd.to_datetime(start_date)
        end_date = pd.to_datetime(end_date)
        
        if start_date == end_date:
            one_day = True
        else:
            one_day = False
        
        df = pd.DataFrame.from_dict(json_dict)
        df['date'] = pd.to_datetime(df['date'])

        if one_day:
            date_df = df.loc[df['date'] == start_date ]
        else:
            date_df = df.loc[(df['date'] >= start_date) & (df['date'] <= end_date)]

        return date_df


    def cleanup_temp_and_mem(self):
        """removes the entire temp_data tree and removes all values in json_data."""
        shutil.rmtree('temp_data')
        self.json_data = None
