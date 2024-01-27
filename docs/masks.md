---
title: Geographic Masks
---

## What is Donut Masking

At its most basic, donut masking is an anonymization technique that works by randomly displacing each point between a specified minimum and maximum distance, as pictured below. This makes it a stronger form of random perturbation, which uses no minimum distance and thus runs the risk of insufficiently anonymizing points. MaskMyPy offers donut masking using the [`Donut`][maskmypy.Donut] masking class.

![Donut masking diagram](assets/donutmasking.png)

Donut masking can be further strengthened by adding some form of population data into the mix. As one can imagine, a point in a downtown core won't need to be displaced nearly as far as a point in the surrounding suburbs to achieve similar levels of anonymity. As such, MaskMyPy offers two additional donut masking classes to help take population density into account: `Donut_Multiply` and `Donut_K`. Both masks require a context layer of polygons containing population counts (e.g. census tracts), but leverage this information in different ways.

[`Donut_Multiply`][maskmypy.Donut_Multiply] works by multiplying masking distances based on the relative population density of the polygon it falls within. This means that points in the most dense areas of a given dataset will have their masking distance multiplied by 1, whereas points within the least dense areas of that same dataset will have their masking distance multiplied by 5. Of course, this multiplier is configurable, 5 is just the default.

[`Donut_K`][maskmypy.Donut_K] works a bit differently. Rather than taking a range of masking distances as input, `Donut_K` takes a desired level of anonymity as input, then figures out the masking distances that are required to achieve that. This level of anonymity is known as _k-anonymity_, and essentially refers to the size of crowd that the point (theoretically) blends into.

There is a caveat to these population-based methods, however: MaskMyPy is only able to factor in the population density of the immediate polygon that the point falls within. This means that if there are neighboring polygons with significantly different population densities, they will not be accounted for. Note that the [`estimate_k`](tools.md#maskmypy.tools.estimate_k) tool _will_ do this disaggregation and will therefore return different, but more accurate values. So as always, be careful, understand your data, and validate that the masked data is sufficiently protected.

## Example Usage

To perform donut masking on a GeoDataFrame containing secret points with a range of 100 to 1000 meters:

```python
from maskmypy import Donut

donutmask = Donut(
    secret=my_secret_gdf, # Name of the secret GeoDataFrame.
    min_distance=100, # The minimum possible distance the points are displaced.
    max_distance=1000) # The maximum possible distance that points are displaced.

donutmask.run() # Execute the mask.

masked = donutmask.mask # A masked GeoDataFrame.
```

To perform more robust donut masking using census data to target a k-anonymity range, a containment layer to prevent points from being displaced to other counties, and a column describing the displacement distance of each point:

```python
from maskmypy import Donut_K

donutmask = Donut_K(
    secret=my_secret_gdf, # Name of the secret GeoDataFrame
    population=census_tracts, # Name of the GeoDataFrame containing population polygons.
    pop_col='pop', # Name of the column containing the population field.
    min_k=10, # The minimum target k-anonymity value.
    max_k=100, # The maximum target k-anonymity value.
    distribution='gaussian', # The distribution to use when displacing points.
    container=county_polygons) # Optional, a GeoDataFrame used to ensure that points do not leave a particular area.

donutmask.run(displacement=true) # Execute the mask and add a column describing displacement distance.

masked = donutmask.mask
```

## Reference

::: maskmypy.donut
    options:  
      show_root_heading: false
      show_root_toc_entry: false
      show_root_members_full_path: false

---

## What is Street Masking

Street masking automatically downloads OpenStreetMap data and uses it to geographically mask your secret points. It provides some of the advantages of population-based masks without requiring the user to hunt down any additional data. It works by first downloading the road network, snapping each secret point to the nearest node on the network (e.g. an intersection or dead end), and then calculating the average network-distance between that node and a pool of the closest _n_ nodes. Note that _n_ is randomly determined for each point from a specified range between `min_depth` and `max_depth`. This average distance is used as the target displacement distance. Finally, it selects a node from the pool whose network-distance from the starting node is closest to the target displacement distance.

You can read more about street masking in [this peer reviewed article](https://ij-healthgeographics.biomedcentral.com/articles/10.1186/s12942-020-00219-z).

![Street masking diagram](assets/streetmasking.png)
_(Note: this diagram is slightly dated as street masking now includes a randomization element. Specifically, depth values are now provided as a range within which a value is selected at random for each point. This makes it more difficult for an attacker to re-identify any given masked point.)_

## Example Usage

To street mask a GeoDataFrame containing secret points with a search-depth range of 20-30 nodes into the street network:

```python
from maskmypy import Street

streetmask = Street(
    secret=my_secret_gdf, # Name of the secret GeoDataFrame.
    min_depth=20, # The minimum depth into the street network that will be traversed.
    max_depth=30, # The maximum depth into the street network that will be traversed.
    seed=12957134581, # A seed value to ensure reproducible results.
    address=address_points_gdf) # Layer of address points used in the next line to calculate k-anonymity.


streetmask.run(calculate_k=true) # Execute the mask and add a column describing the k-anonymity of each point.

masked = streetmask.mask
```

## Reference
::: maskmypy.street
    options:  
      show_root_heading: false
      show_root_members_full_path: false
