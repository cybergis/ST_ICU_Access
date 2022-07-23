import geopandas as gpd
import pandas as pd
import multiprocessing as mp
from utils import local_OD_Matrix_unpacker
import itertools

# Import files
# Census Block Groups, CRS: epsg 3081
demand = gpd.read_file('./data/original_data/demand_related/census_tract_projected.json')
demand = demand.set_index('GEOID')

# Locations of Hospitals, CRS: epsg 3081
supply = gpd.read_file('./data/original_data/supply_related/hospital_geocode.json')
supply = supply.set_index('HC_ID')
supply['FIPS'] = supply['FIPS'].astype(str)

# Look up table of the distance between supply (Hospitals) and demand (Census Block Groups)
within_dist = pd.read_csv('../data/access/input_files/mobility_lookup.csv')
within_dist = within_dist.drop(columns=['Unnamed: 0'])
within_dist['GEOID'] = within_dist['GEOID'].astype(str)
within_dist['trvl_time'] = -999


if __name__ == "__main__":
    pool = mp.Pool(8)
    pool.map(local_OD_Matrix_unpacker,
             zip(supply['FIPS'].unique().tolist(),
                 #['48001', '48003', '48013', '48015', '48017', '48023', '48025', '48035'],
                 itertools.repeat(supply),
                 itertools.repeat(demand),
                 itertools.repeat(within_dist)
                 )
             )
    pool.close()
