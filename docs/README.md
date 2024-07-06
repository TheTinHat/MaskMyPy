<div style="text-align:center; width: 100%;"><img src="assets/logo.png" width=400px style="max-width: 400px;"></div>

---

[![Tests](https://github.com/TheTinHat/MaskMyPy/actions/workflows/test-package.yml/badge.svg?branch=master)](https://github.com/TheTinHat/MaskMyPy/actions/workflows/test-package.yml)
![License](https://img.shields.io/github/license/TheTinHat/MaskMyPy)
[![PyPi](https://img.shields.io/pypi/v/maskmypy)](https://pypi.org/project/maskmypy/)

# MaskMyPy

## Key Features

- Python tools for anonymizing geographic point data held in GeoDataFrames.
- Includes four masks: donut, street, location swap, and voronoi.
- Evaluation tools for assessing information loss and privacy protection.
- An `Atlas` tool that allows for rapid experimentation of mask types and parameters.

## Introduction

MaskMyPy ([GitHub](https://github.com/TheTinHat/MaskMyPy) | [Docs](https://thetinhat.github.io/MaskMyPy/)) is a Python package that performs geographic masking on [GeoDataFrames](http://geopandas.org/data_structures.html). In other words, it helps with anonymizing point data, such as confidential home addresses. It currently offers four main approaches towards anonymization: donut masking, street masking, location swapping, and voronoi masking.

MaskMyPy also offers a range of [analysis tools](analysis.md) to help assess mask performance. These include functions for calculating:

- k-anonymity using either address points or population polygons (e.g. census data)
- displacement distance
- clustering based on Ripley's K-function
- nearest neighbor distances
- and more!

### Use Cases: Why Geographic Masks?

Geographic masks are techniques that protect confidential point data while still maintaining important spatial patterns within the dataset. While aggregation is often employed for privacy protection (as done by many censuses), aggregation reduces the usefulness of the data for statistical analysis. Example use cases for geographic masks include:

- A epidemiologist wants to release a dataset of patient addresses to help other researchers study the spread of a given disease. They also want anonymized points to remain inside the same census tract after masking to preserve statistical attributes. By utilizing donut masking and a containment layer, they are able to publish the dataset without compromising patient privacy, the location of important disease clusters, or census attributes.
- A mobile app developer wants to publish an end-of-year blog post with a map showing where their users have posted from, but is concerned about the privacy of their users. They utilize street masking to randomly displace points to nearby intersections on the street network before making the post.
- A criminologist wants to share a map of burglary locations but does not want to compromise victim privacy. They anonymize the dataset using street masking. To validate that their mask was effective they then calculate the spatial k-anonymity and displacement distance of each anonymized point. Realizing that some points were insufficiently protected, they tweak their masking parameters and repeat the process. Happy with the new results, they release the masked map.

### Disclaimer

_MaskMyPy is offered as-is, without warranty of any kind. Geographic masking is a hard problem that requires informed decisions and validation. MaskMyPy provides helpful tools for geographic masking, but does not replace expertise._

## Installation

```shell
pip install maskmypy
```

To also install optional dependencies (such as those required for displacement mapping):

```shell
pip install maskmypy[extra]
```

## Quickstart

### Masking/Anonymization

The following snippet applies a 500 meter donut mask to a GeoDataFrame of secret (e.g. sensitive) points:

```python
from maskmypy import donut
import geopandas as gpd
secret_points = gpd.read_file('secret_points.shp')
masked_points = donut(secret_points, min=50, max=500)
```

Unless specified, MaskMyPy uses the same units of distance as the CRS of the input secret points. If our secret points instead used a CRS that is in feet, then our mask would have had a maximum distance of 500 feet.

### Evaluation

If we wanted to analyze how effective this mask was, we can leverage many of the analysis tools MaskMyPy offers by using a convenience function called `evaluate()`:

```python
from maskmypy import analysis
census_polygons = gpd.read_file('census.shp')

# Return a dictionary containing evaluation results
mask_stats = analysis.evaluate(
  sensitive_gdf=secret_points,
  candidate_gdf=masked_points,
  population_gdf=census_polygons,
  population_column="population"
)
```

### The Atlas

The `Atlas()` class makes it easy to both mask datasets and evaluate new masks. It acts as a type of manager that allows you to quickly test any number of combinations of masks and their associated parameters, automatically performing the evaluation for you and keeping track of the results. Each result is referred to as a 'candidate' and is kept in a list at `Atlas.candidates`, which you can also access by slicing the Atlas itself (e.g. `Atlas[0]`).

```python
import geopandas as gpd
from maskmypy import Atlas, donut, street, locationswap

# Load some data
points = gpd.read_file('sensitive_points.shp')
addresses = gpd.read_file('address_points.shp')

# Instantiate the Atlas
atlas = Atlas(points, population=addresses)

# The mask() method takes any mask callable, with its arguments simply specified as keyword arguments
atlas.mask(donut, low=10, high=100) # Donut mask with small distances.
atlas.mask(donut, low=50, high=500) # Donut mask with larger distances.

atlas.mask(street, low=5, high=15) # Street masking.
atlas.mask(locationswap, low=50, high=500, address=addresses) # Location swapping.

atlas.as_df() # Return a nicely formatted dataframe detailing the results of each mask.

atlas.sort("k_min", desc=True) # Sort the list of results by minimum k_anonymity.

# The Atlas doesn't keep every masked gdf after it's done evaluating it. This is done to save memory.
# But we can reproduce an *exact copy* using the `gen_gdf()` method!
# The number represents the index in the candidate list. We sorted it by minimum k_anonymity, so
# this will return the masked gdf with the highest minimum k-anonymity.
masked_gdf = atlas.gen_gdf(0)
```

## Contribute

Any and all efforts to contribute are welcome, whether they include actual code or just feedback. Please find the GitHub repo [here](https://github.com/TheTinHat/MaskMyPy).

Developers, please keep the following in mind:

- You can install the necessary development tools by cloning the repo and running `pip install -e .[develop]`.
- MaskMyPy uses `black` with a line length of 99 to format the codebase. Please run `black -l 99` before submitting any pull requests.
- Run `pytest` from the project root before submitting any code changes to ensure that your changes do not break anything.
- Please include tests with any feature contributions.
