import geopandas as gpd
from atlas import Atlas, Candidate
import time

gdf = gpd.read_file("../tests/data/100_test_points.shp")
atlas = Atlas(
    gdf, directory="/home/david/test/test_gdf/", name="gdftest", keep_last=15, autosave=True
)

for i in range(20):
    atlas.set(Candidate(gdf, parameters={"id": i, "title": f"Release_Candidate {i}"}))
    time.sleep(0.01)

atlas.save_atlas()
del atlas

atlas = Atlas.open_atlas("/home/david/test/test_gdf/")
breakpoint()
