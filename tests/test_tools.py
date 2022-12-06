import geopandas as gpd


def get_test_data():
    gpkg = gpd.read_file("test_data.gpkg")

    layers = {}
    for layer in gpkg:
        layers[layer] = gpkg[layer]

    return layers
