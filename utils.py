import osmnx as ox
import networkx as nx
from tqdm import tqdm
import pandas as pd
import numpy as np
import datetime

# DISTANCE DECAY
minutes = [0, 5, 10, 15, 20, 25, 30, 35, 40, 45, 60]
weights = {0: 1, 5: 0.9459, 10: 0.7544, 15: 0.5511, 20: 0.3993, 25: 0.2957, 30: 0.2253, 35: 0.1765, 40: 0.1417, 45: 0.1161, 60: 0.0832}


# Necessary functions
def find_nearest_osm(network, gdf):
    for idx, row in tqdm(gdf.iterrows(), total=gdf.shape[0]):
        if row.geometry.geom_type == 'Point':
            nearest_osm = ox.distance.nearest_nodes(network,
                                                    X=row.geometry.x,
                                                    Y=row.geometry.y
                                                    )
        elif row.geometry.geom_type == 'Polygon' or row.geometry.geom_type == 'MultiPolygon':
            nearest_osm = ox.distance.nearest_nodes(network,
                                                    X=row.geometry.centroid.x,
                                                    Y=row.geometry.centroid.y
                                                    )
        else:
            print(row.geometry.geom_type)
            continue

        gdf.at[idx, 'nearest_osm'] = nearest_osm

    return gdf


def remove_weakly_connected_network(network):
    _nodes_removed = len([n for (n, deg) in network.out_degree() if deg == 0])
    network.remove_nodes_from([n for (n, deg) in network.out_degree() if deg == 0])
    for component in list(nx.strongly_connected_components(network)):
        if len(component) < 10:
            for node in component:
                _nodes_removed += 1
                network.remove_node(node)

    print("Removed {} nodes ({:2.4f}%) from the OSMNX network".format(_nodes_removed, _nodes_removed / float(
        network.number_of_nodes())))
    print("Number of nodes: {}".format(network.number_of_nodes()))
    print("Number of edges: {}".format(network.number_of_edges()))

    return network


def local_OD_Matrix(fips_, supply, demand, within_dist):
    """
    :param fips_: (str) fips code of the current county of calculating OD matrix
    :param supply: (GeoDataFrame) Hospitals in the current FIPS
    :param demand: (GeoDataFrame) Census Block Groups within 100 miles of the current FIPS
    :param within_dist: (DataFrame) Long form that has the IDs of supply(HC_ID) and demand (GEOID)
                                    and the distance between two locations.
    :return: None
    """

    # fips_ = '48453'
    temp_supply = supply.loc[supply['FIPS'] == fips_]
    temp_within = within_dist.loc[within_dist['HC_ID'].isin(temp_supply.index)]
    temp_demand = demand.loc[demand.index.isin(temp_within['GEOID'])]

    print(f"FIPS: {fips_}, Supply count: {temp_supply.shape[0]}, Demand count: {temp_demand.shape[0]}")

    # A list of counties accessible from the hospitals (temp_supply)
    osm_list = temp_within.apply(lambda x: x['GEOID'][0:5], axis=1).unique()

    # Appending OSM networks
    G = ox.load_graphml(f'./data/original_data/OSM_Network/OSM_{osm_list[0]}.graphml',
                        edge_dtypes={'maxspeed_meters': float, 'time': float})
    for i in range(1, len(osm_list)):
        H = ox.load_graphml(f'./data/original_data/OSM_Network/OSM_{osm_list[i]}.graphml',
                            edge_dtypes={'maxspeed_meters': float, 'time': float})
        print(f'OSM_Network at {osm_list[i]} is appended to {osm_list[0]}. {i+1} out of {len(osm_list)}')
        G = nx.compose(G, H)

    G = remove_weakly_connected_network(G)

    # Find the nearest OSM nodes from the supply and demand.
    temp_demand = find_nearest_osm(G, temp_demand)
    temp_supply = find_nearest_osm(G, temp_supply)

    # Calculate OD Matrix of a county (fips_)
    for idx_s, row_s in tqdm(temp_supply.iterrows(), total=temp_supply.shape[0]):

        # Draw a service area from a hopsital and obtain the dictionary of {OSMID: travel time}
        temp_catchment = nx.single_source_dijkstra_path_length(G, int(row_s['nearest_osm']), 75, weight='time')

        # Select only OSMIDs exist in temp_demand and update `trvl_time` column of `temp_within`.
        for key, val in temp_catchment.items():
            if key in temp_demand.nearest_osm.to_list():
                # Obtain GEOID of demand based on its nearest OSMID.
                reachable_demand = temp_demand.loc[temp_demand.nearest_osm == key].index[0]
                #             print(idx_s, reachable_demand, round(val, 3))

                # Update `trvl_time` column based on the catchment query.
                temp_within.loc[(temp_within['HC_ID'] == idx_s)
                                & (temp_within['GEOID'] == reachable_demand), 'trvl_time'] = val

    # Locations where be able to calculate with the catchment.
    updated_vals = temp_within.loc[(temp_within['HC_ID'].isin(temp_supply.index)) &
                                   (temp_within['GEOID'].isin(temp_demand.index)) &
                                   (temp_within['trvl_time'] != -999)
                                   ]
    updated_vals.to_csv(f'./data/original_data/OD_Matrix/Hospitals_in_{fips_}.csv')

    # Locations where not be able to calculate with the catchment.
    not_updated_vals = temp_within.loc[(temp_within['HC_ID'].isin(temp_supply.index)) &
                                       (temp_within['GEOID'].isin(temp_demand.index)) &
                                       (temp_within['trvl_time'] == -999)
                                   ]

    # for idx, row in tqdm(not_updated_vals.iterrows(), total=not_updated_vals.shape[0]):
    #     temp_trvl_time = nx.shortest_path_length(G=G,
    #                                              source=int(temp_supply.loc[row['HC_ID'], 'nearest_osm']),
    #                                              target=int(temp_demand.loc[row['GEOID'], 'nearest_osm']),
    #                                              weight='time',
    #                                              method='dijkstra'
    #                                              )
    #     not_updated_vals.at[idx, 'trvl_time'] = temp_trvl_time

    not_updated_vals.to_csv(f'./data/original_data/OD_Matrix/Hospitals_in_{fips_}_non.csv')


def local_OD_Matrix_unpacker(args):
    return local_OD_Matrix(*args)


def E2SFCA_Step1(supply_loc, supply_var, demand_var, mobility, date_):
    # date_ = '06/01/2020'
    step1 = pd.DataFrame(index=supply_loc.index, columns=[date_])

    for s_idx in tqdm(step1.index):
        temp_s_count = supply_loc.at[s_idx, 'ICU_Beds']
        temp_s_avail = supply_var.loc[supply_loc.loc[s_idx, 'TSA'], date_]
        temp_supply = temp_s_count * temp_s_avail

        temp_ctmt = mobility.loc[mobility['HC_ID'] == s_idx]

        temp_demand = 0
        for idx, minute in enumerate(minutes):
            if idx != 0:
                temp_ctmt_geoid = temp_ctmt.loc[(minutes[idx - 1] < temp_ctmt['trvl_time'])
                                                & (temp_ctmt['trvl_time'] <= minute), 'GEOID'].to_list()
                temp_demand += demand_var.loc[temp_ctmt_geoid, date_].sum() * weights[minute]
        temp_ratio = temp_supply / temp_demand
        step1.at[s_idx, date_] = temp_ratio

    step1[date_] = step1[date_].replace(np.inf, 0)

    return step1

def E2SFCA_Step2(step1_, demand_loc, mobility, date_):
    step2 = pd.DataFrame(index=demand_loc.index, columns=[date_])
    step2 = step2.fillna(0.0)

    for d_idx in tqdm(step2.index):
        temp_ctmt_2 = mobility.loc[mobility['GEOID'] == int(d_idx)]
        temp_ratio = 0
        for idx, minute in enumerate(minutes):
            if idx != 0:
                temp_ctmt_hc_id = temp_ctmt_2.loc[(minutes[idx - 1] < temp_ctmt_2['trvl_time'])
                                                  & (temp_ctmt_2['trvl_time'] <= minute), 'HC_ID'].to_list()
                temp_ratio += step1_.loc[temp_ctmt_hc_id, date_].sum() * weights[minute]

        step2.at[d_idx, date_] = temp_ratio

    return step2


def measure_accessibility(supply_loc, demand_loc, supply_var, demand_var, mobility, date_):
    print(f'Accessibility Measure on {date_}')

    step1_df = E2SFCA_Step1(supply_loc, supply_var, demand_var, mobility, date_)
    step2_df = E2SFCA_Step2(step1_df, demand_loc, mobility, date_)

    step1_df.to_csv(f'./data/access/ICU_access_measures/keeling/acc_step1_{date_.replace("/", "_")}.csv')
    step2_df.to_csv(f'./data/access/ICU_access_measures/keeling/acc_step2_{date_.replace("/", "_")}.csv')

    return step1_df, step2_df


def measure_accessibility_unpacker(args):
    return measure_accessibility(*args)


def calculate_focus_date_dict(from_date, to_date, delta_days):
    # from_date = '07/01/2020'
    # to_date = '12/31/2021'

    start_date = datetime.datetime.strptime(from_date, "%m/%d/%Y")
    end_date = datetime.datetime.strptime(to_date, "%m/%d/%Y")

    focus_date_list = []
    delta = datetime.timedelta(days=delta_days)
    while start_date <= end_date:
        focus_date_list.append(start_date.strftime("%m/%d/%Y"))
        start_date += delta

    # Make a dictionary that has keys as target date and values as the date that should be averaged.
    focus_date_dict = {}
    time_delta = [3, 2, 1, 0, -1, -2, -3]

    for idx, date in enumerate(focus_date_list):
        temp_list = []
        for delta in time_delta:
            temp_list.append(
                str(
                    (datetime.datetime.strptime(focus_date_list[idx], "%m/%d/%Y") - datetime.timedelta(days=delta)
                     ).strftime("%m/%d/%Y"))
            )

        focus_date_dict[date] = temp_list

    # Manually enter the dates that would have missing values
    focus_date_dict['07/01/2020'] = ['07/01/2020', '07/02/2020', '07/03/2020', '07/04/2020']
    focus_date_dict['07/02/2020'] = ['07/01/2020', '07/02/2020', '07/03/2020', '07/04/2020', '07/05/2020']
    focus_date_dict['07/03/2020'] = ['07/01/2020', '07/02/2020', '07/03/2020', '07/04/2020', '07/05/2020', '07/06/2020']
    focus_date_dict['12/29/2021'] = ['12/26/2021', '12/27/2021', '12/28/2021', '12/29/2021', '12/30/2021', '12/31/2021']
    focus_date_dict['12/30/2021'] = ['12/27/2021', '12/28/2021', '12/29/2021', '12/30/2021', '12/31/2021']
    focus_date_dict['12/31/2021'] = ['12/28/2021', '12/29/2021', '12/30/2021', '12/31/2021']

    return focus_date_dict


