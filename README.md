# MaskMyPy
MaskMyPy is a (very alpha) Python package that performs geographic masking on [GeoPandas geodataframes](http://geopandas.org/data_structures.html). It offers two main methods: street masking and donut masking. 

MaskMyPy also supports k-anonymity estimation using population data and k-anonymity calculation using address data, as well as the calculation of displacement distance between sensitive and masked points.

[![Downloads](https://pepy.tech/badge/maskmypy)](https://pepy.tech/project/maskmypy)

**Disclaimer**: *MaskMyPy is offered as-is, without warranty of any kind. Geographic masking is a hard problem that requires informed decisions and validation. MaskMyPy provides helpful tools for geographic masking, but does not replace expertise.*

## Installation
MaskmyPy is pip-installable, but relies on [osmnx](https://anaconda.org/conda-forge/osmnx). If you do not have it installed, first get it using Anaconda:
```
conda install -c conda-forge osmnx
```
Then, install MaskMyPy using pip:
```
pip install maskmypy
```

## Street Masking
Street masking automatically downloads OpenStreetMap road network data and uses it to geographically mask your sensitive points. It works by first downloading the road network data, snapping each sensitive point to the nearest node on the network (an intersection or dead end), and then calculating the average network-distance between that node and a pool of the closest x number of nodes (e.g. the clsoest 20 nodes on the network, known as the search depth). This average distance is the target displacement distance. Finally, it selects a node from the pool whose network-distance from the starting node is closest to the target displacement distance. 

**Usage:** To street mask a geodataframe containing sensitive points with a search-depth value of 20, the code would be as follows:

```
from maskmypy import Street

streetmask = Street(
    sensitive_gdf, # Name of the sensitive geodataframe
    depth=20, # The search depth value used to calculate displacement distances. 
    extent_expansion_distance=2000, # Used to download road network data surrounding the study area. Needs to be sufficiently large to reduce edge effects. Increasing reduces edge effects, but uses more memory.
    max_street_length=500) # Optional, but recommended that you read below for full explanation of what this does.


streetmask.execute() # Single threaded by default. Add `parallel=True` as parameter to run on all CPU cores, drastically increasing performance.

masked_gdf = streetmask.masked
```

**About max_street_length**: when snapping points to the street network, the algorithm checks to make sure that the nearest node is actually connected to the network and has neighbors that are no more than max_street_length away (in meters). If it does not, then the next closest viable node is selected, checked, and so on. This acts as a sanity check to prevent extremely large masking distances. Feel free to change this to whatever you feel is appropriate. 



## Donut Masking

**Usage:** 
To perform basic donut geomasking on a geodataframe containing sensitive points, with a maximum displacement distance of 500 meters and an minimum displacement distance of 20% of the maximum distance (i.e. 100 meters), the code would look like this:

```
from maskmypy import Donut

donutmask = Donut(
    sensitive_gdf=sensitive_gdf, # Name of the sensitive geodataframe
    max_distance=250, # The maximum possible distance that points are displaced
    donut_ratio=0.1, # The ratio used to define the minimum distance points are displaced
    distribution='uniform', # The distribution to use when displacing points. Other options include 'gaussian' and 'areal'. 'Areal' distribution means points are more likely to be displaced further within the range.
    container_gdf=container_gdf) # Optional, a geodataframe used to ensure that points do not leave a particular area. 

donutmask.execute()

masked_gdf = donutmask.masked
```

To perform full donut geomasking (i.e. using census data and a target k-anonymity range rather than distance range) with a maximum k-anonymity of 1000 and minimum of 200, and a census geodataframe called population_gdf, the code would appear as follows:

```
from maskmypy import Donut_MaxK

donutmask = Donut_MaxK(
    sensitive_gdf, # Name of the sensitive geodataframe
    population_gdf=population_gdf, # Name of the census geodataframe
    population_column='pop', # Name of the column containing the population field
    max_k_anonymity=1000, # The maximum possible k-anonymity value
    donut_ratio=0.2, # The ratio used to define the minimum possible k-anonymity value.
    distribution='uniform', # The distribution to use when displacing points. Other options include 'gaussian' and 'areal'. 'Areal' distribution means points are more likely to be displaced further within the range.
    container_gdf=container_gdf) # Optional, a geodataframe used to ensure that points do not leave a particular area. 

donutmask.execute()

masked_gdf = donutmask.masked
```


## K-Anonymity
Maskmypy is able to calculate the k-anonymity of each point after masking. Two methods are available for this: estimates, and exact calculations. Estimates of k-anoynmity are inferred from census data, and assume a homogeneously distributed population within each census polygon. Address-based k-anonymity is more accurate and uses actual home address data to calculate k-anonymity.

### Estimate K-Anonymity
**Usage:** 
After the data has been masked, estimating k-anoynmity using census data would look like this and will add a column to the masked geodataframe:
```
mask.k_anonymity_estimate(
    population_gdf=population_gdf, # Name of the census geodataframe. Not necessary if you already included this parameter in the original masking steps.
    population_column='pop') # Name of the column containing the population field. Not necessary if you already included this parameter in the original masking steps.
```

### Calculate K-Anonymity
**Usage:** 
After the data has been masked, calcualting address-based k-anoynmity would look like this and will add a column to the masked geodataframe:
```
mask.k_anonymity_actual(address_points_gdf='') # Name of the geodataframe including address points. 
```

## Displacement Distance
**Usage:** 
To add a column to the masked geodataframe that includes the actual displacement distances (in meters), one can just execute:
```
mask.displacement_distance()
```

