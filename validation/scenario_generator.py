# Copyright 2020 (c) Cognizant Digital Business, Evolutionary AI. All rights reserved. Issued under the Apache 2.0 License.

import numpy as np
import pandas as pd

ID_COLS = ['CountryName',
           'RegionName',
           'Date']
NPI_COLUMNS = ['C1_School closing',
               'C2_Workplace closing',
               'C3_Cancel public events',
               'C4_Restrictions on gatherings',
               'C5_Close public transport',
               'C6_Stay at home requirements',
               'C7_Restrictions on internal movement',
               'C8_International travel controls',
               'H1_Public information campaigns',
               'H2_Testing policy',
               'H3_Contact tracing']
# From https://github.com/OxCGRT/covid-policy-tracker/blob/master/documentation/codebook.md
MIN_NPIS = [0] * len(NPI_COLUMNS)
MAX_NPIS = [3, 3, 2, 4, 2, 3, 2, 4, 2, 3, 2]  # Sum is 30
INCEPTION_DATE = pd.to_datetime("2020-01-01", format='%Y-%m-%d')


def generate_scenario(start_date_str, end_date_str, raw_df, countries=None, scenario="Freeze"):
    """
    Generates a scenario: a list of intervention plans, with history since 1/1/2020.
    Args:
        start_date_str: start_date from which to apply the scenario. None to apply from last known date
        end_date_str: end_date of the data
        raw_df: the original data frame containing the raw data
        countries: a list of CountryName, or None for all countries
        scenario:
            - "Freeze" to apply the last available NPIs to every day between start_date and end_date, included
            - "MIN" to set all NPIs to 0 (i.e. plan is to take no measures)
            - "MAX" to set all NPIs to maximum values (i.e. plan is to do everything possible)
            - an array of size "number of days between start_date and end_date"
            containing for each day the array of integers of NPI_COLUMNS lengths to use.
        In case NPIs are not know BEFORE start_date, the last known ones are carried over.

    Returns: a Pandas DataFrame

    """
    start_date = pd.to_datetime(start_date_str, format='%Y-%m-%d')
    end_date = pd.to_datetime(end_date_str, format='%Y-%m-%d')

    if start_date:
        if end_date <= start_date:
            raise ValueError(f"end_date {end_date} must be after start_date {start_date}")

        if start_date < INCEPTION_DATE:
            raise ValueError(f"start_date {start_date} must be on or after inception date {INCEPTION_DATE}")

    ips_df = raw_df[ID_COLS + NPI_COLUMNS]

    # Filter on countries
    if countries:
        ips_df = ips_df[ips_df.CountryName.isin(countries)]

    # Fill any missing "supposedly known" NPIs by assuming they are the same as previous day, or 0 if none is available
    for npi_col in NPI_COLUMNS:
        ips_df.update(ips_df.groupby(['CountryName', 'RegionName'])[npi_col].ffill().fillna(0))

    new_rows = []
    for country in ips_df.CountryName.unique():
        all_regions = ips_df[ips_df.CountryName == country].RegionName.unique()
        for region in all_regions:
            ips_gdf = ips_df[(ips_df.CountryName == country) &
                             (ips_df.RegionName == region)]
            country_name = ips_gdf.iloc[0].CountryName
            region_name = ips_gdf.iloc[0].RegionName
            last_known_date = ips_gdf.Date.max()
            # If the start date is not specified, start from the day after the last known date
            if not start_date_str:
                start_date = last_known_date + np.timedelta64(1, 'D')
            # If the last known date is BEFORE the start date, start applying the scenario at last_known date
            current_date = min(last_known_date + np.timedelta64(1, 'D'), start_date)
            scenario_to_apply = 0
            while current_date <= end_date:
                new_row = [country_name, region_name, current_date]
                if current_date < start_date:
                    # We're before the scenario start date. Carry over last known NPIs
                    npis = list(ips_gdf[ips_gdf.Date == last_known_date][NPI_COLUMNS].values[0])
                else:
                    # We are between start_date and end_date: apply the scenario
                    if scenario == "MIN":
                        npis = MIN_NPIS
                    elif scenario == "MAX":
                        npis = MAX_NPIS
                    elif scenario == "Freeze":
                        if start_date <= last_known_date:
                            day_before_start = max(INCEPTION_DATE, start_date - np.timedelta64(1, 'D'))
                            npis = list(ips_gdf[ips_gdf.Date == day_before_start][NPI_COLUMNS].values[0])
                        else:
                            npis = list(ips_gdf[ips_gdf.Date == last_known_date][NPI_COLUMNS].values[0])
                    else:
                        npis = scenario[scenario_to_apply]
                        scenario_to_apply = scenario_to_apply + 1
                new_row = new_row + npis
                new_rows.append(new_row)
                # Move to next day
                current_date = current_date + np.timedelta64(1, 'D')
    if new_rows:
        future_rows_df = pd.DataFrame(new_rows, columns=ips_df.columns)
        # Delete any old row that might have been replaced by a scenario one
        replaced_dates = list(future_rows_df["Date"].unique())
        ips_df = ips_df[ips_df["Date"].isin(replaced_dates) == False]
        # Append the new rows
        ips_df = ips_df.append(future_rows_df)
        # Sort
        ips_df.sort_values(by=ID_COLS, inplace=True)

    return ips_df
