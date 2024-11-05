import pandas as pd

fip_to_name = pd.read_csv("src/scenarios_hpc_azure/data/fips_to_name.csv")
state_pops_map = pd.read_csv(
    "src/scenarios_hpc_azure/data/CenPop2020_Mean_ST.csv"
)
state_to_hhs_region = pd.read_csv(
    "src/scenarios_hpc_azure/data/state_to_hhs_region.csv"
)

# add the USA to the population frame
usa_pop_row = pd.DataFrame(
    [
        [
            "US",
            "United States",
            sum(state_pops_map["POPULATION"]),
            "+44.582076",  # latitude
            "+103.461760",  # longitude
        ]
    ],
    columns=state_pops_map.columns,
)
state_pops_map = pd.concat([state_pops_map, usa_pop_row], ignore_index=True)

# add the stid to identify each row as country, state, district, or hhsregion
fip_to_name["stid"] = "state"
fip_to_name.loc[fip_to_name["stname"] == "United States", "stid"] = "country"
fip_to_name.loc[
    fip_to_name["stname"] == "District of Columbia", "stid"
] = "district"
fip_to_name.loc[fip_to_name["stname"] == "Puerto Rico", "stid"] = "territory"

# merge all the dataframes together to get population, hhsregion, etc
state_abr_and_pop = pd.merge(
    left=state_pops_map,
    right=fip_to_name[["stname", "stusps", "stid"]],
    how="left",
    left_on="STNAME",
    right_on="stname",
).drop("stname", axis=1)
all_combined = pd.merge(
    left=state_abr_and_pop, right=state_to_hhs_region, on="stusps", how="left"
)

# sum up the states by their hhsregion and add those rows onto the df
# create the HHS regions by selecting all states under each `hhsregion` value
add_hhs_regions = all_combined.groupby(by="hhsregion").sum().reset_index()
add_hhs_regions["LATITUDE"] = None  # does not quite make sense for a region
add_hhs_regions["LONGITUDE"] = None
add_hhs_regions["hhsregion"] = add_hhs_regions["hhsregion"].astype(int)
add_hhs_regions["STNAME"] = [
    "hhs" + str(i) for i in add_hhs_regions["hhsregion"]
]
# add commas between each abbreviation
add_hhs_regions["stusps"] = [
    ",".join(s[i : i + 2] for i in range(0, len(s), 2))
    for s in add_hhs_regions["stusps"]
]
add_hhs_regions["stid"] = "hhsregion"

# append those hhsregions to the combined df and rename the columns then done
final = pd.concat([all_combined, add_hhs_regions], ignore_index=True)
final.columns = [
    "statefp",
    "stname",
    "population",
    "latitude",
    "longitude",
    "stusps",
    "stid",
    "hhsregion",
]
# reorder the cols
final = final[
    [
        "statefp",
        "stname",
        "stusps",
        "hhsregion",
        "population",
        "stid",
        "latitude",
        "longitude",
    ]
]
final.to_csv("src/scenarios_hpc_azure/data/regions_mapping_combined.csv")
print(final.head())
