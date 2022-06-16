import geopandas as gpd
import pandas as pd
import datetime
import utils
import multiprocessing as mp
import itertools
from tqdm import tqdm


# Import input files
# Supply locations
s_loc = gpd.read_file('./data/access/input_files/hospital_geocode.json')
s_loc = s_loc.set_index('HC_ID')
s_loc = s_loc.fillna(0)

# Demand locations
d_loc = gpd.read_file('./data/access/input_files/census_tract_projected.json')
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



# DISTANCE DECAY
minutes = [0, 5, 10, 15, 20, 25, 30, 35, 40, 45, 60]
weights = {0: 1, 5: 0.9459, 10: 0.7544, 15: 0.5511, 20: 0.3993, 25: 0.2957, 30: 0.2253, 35: 0.1765, 40: 0.1417, 45: 0.1161, 60: 0.0832}


step1 = pd.DataFrame(index=supply_loc.index, columns=['static'])

# Step 1 of E2SFCA
for s_idx in tqdm(step1.index):
    temp_s_count = s_loc.at[s_idx, 'ICU_Beds']
    # temp_s_avail = supply_var.loc[supply_loc.loc[s_idx, 'TSA'], date_]
    temp_supply = temp_s_count

    temp_ctmt = mobility_df.loc[mobility_df['HC_ID'] == s_idx]

    temp_demand = 0
    for idx, minute in enumerate(minutes):
        if idx != 0:
            temp_ctmt_geoid = temp_ctmt.loc[(minutes[idx - 1] < temp_ctmt['trvl_time'])
                                            & (temp_ctmt['trvl_time'] <= minute), 'GEOID'].to_list()
            temp_demand += demand_var.loc[temp_ctmt_geoid, date_].sum() * weights[minute]
    temp_ratio = temp_supply / temp_demand
    step1.at[s_idx, date_] = temp_ratio

step1[date_] = step1[date_].replace(np.inf, 0)