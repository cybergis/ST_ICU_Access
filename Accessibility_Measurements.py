import geopandas as gpd
import pandas as pd
import datetime
import utils
import multiprocessing as mp
import itertools


# Import input files
# Supply locations
s_loc = gpd.read_file('./data/supply_related/hospital_geocode.json')
s_loc = s_loc.set_index('HC_ID')
s_loc = s_loc.fillna(0)

# Demand locations
d_loc = gpd.read_file('./data/demand_related/census_tract_projected.json')
d_loc = d_loc.set_index('GEOID')

# Mobility: OD Matrix between supply and demand locations
mobility_df = pd.read_csv('./data/access/input_files/Precalculated_OD_Matrix.csv')

# Supply daily variation
s_val = pd.read_csv('./data/supply_related/ICU_beds_available_ratio.csv')
s_val = s_val.rename(columns={'Unnamed: 0': 'TSA'})
s_val = s_val.set_index('TSA')

# Demand daily variation
d_val = pd.read_csv('./data/demand_related/estimated_covid_case.csv')
d_val = d_val.set_index('GEOID')
d_val = d_val.drop(columns=['FIPS', 'CTID', 'Pop_Ratio', 'County_Pop'])

# Focus dates of analysis
from_date = '07/01/2020'
to_date = '12/31/2021'

start_date = datetime.datetime.strptime(from_date,  "%m/%d/%Y")
end_date = datetime.datetime.strptime(to_date,  "%m/%d/%Y")

focus_date = []
delta = datetime.timedelta(days=1)
while start_date <= end_date:
    focus_date.append(start_date.strftime("%m/%d/%Y"))
    start_date += delta

if __name__ == "__main__":
    pool = mp.Pool(8)
    pool.map(utils.measure_accessibility_unpacker,
             zip(itertools.repeat(s_loc),
                 itertools.repeat(d_loc),
                 itertools.repeat(s_val),
                 itertools.repeat(d_val),
                 itertools.repeat(mobility_df),
                 focus_date
                )
             )
    pool.close()
