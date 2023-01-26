import geopandas as gpd






def displacement(gdf, candidate_gdf, colname="_displacement"):
    candidate_gdf[colname] = candidate_gdf.geometry.distance(gdf.geometry)
    return candidate_gdf



def estimate_k(sensitive_gdf, candidate_gdf, population_gdf, pop_col="pop"):
    pop_col_adjusted = "_".join([pop_col, "adjusted"])
    gdf["k_est"] = (
        displacement(sensitive_gdf, candidate_gdf)
        .assign(geometry=lambda x: x.geometry.buffer(x["_distance"]), axis=1)
        .pipe(disaggregate, gdf_b=population, gdf_b_col=pop_col)
        .groupby("_index_2")[pop_col_adjusted]
        .sum()
        .round()
    )
    return gdf


def calculate_k(
    secret: gpd.GeoDataFrame, mask: gpd.GeoDataFrame, address: gpd.GeoDataFrame
) -> gpd.GeoDataFrame:
    mask_tmp = displacement(secret, mask).assign(
        geometry=lambda x: x.buffer(x["_distance"])
    )
    mask["k_calc"] = (
        sjoin(address, mask_tmp, how="left", rsuffix="mask")
        .groupby("index_mask")
        .size()
    )
    mask.fillna({"k_calc": 0}, inplace=True)
    return sanitize(mask)

def disaggregate(gdf_a, gdf_b, gdf_b_col):
    new_col = "_".join([gdf_b_col, "adjusted"])
    gdf_b["_b_area"] = gdf_b.geometry.area
    gdf = sjoin(gdf_a, gdf_b, how="left", rsuffix="b").rename_axis("_index_2").reset_index()
    gdf.geometry = gdf.apply(
        lambda x: x.geometry.intersection(gdf_b.at[x["index_b"], "geometry"]),
        axis=1,
    )
    gdf["_intersected_area"] = gdf.geometry.area

    for i, _ in enumerate(gdf.index):
        fragments = gdf.loc[gdf["_index_2"] == i, :]
        for index, row in fragments.iterrows():
            area_pct = row["_intersected_area"] / row["_b_area"]
            gdf.at[index, new_col] = row[gdf_b_col] * area_pct
    return gdf
