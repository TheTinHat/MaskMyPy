<div style="text-align:center; width: 100%;"><img src="assets/logo.png" width=400px style="max-width: 400px;"></div>

-----

Python tools for anonymizing geographic data.

![Master Tests](https://img.shields.io/github/checks-status/TheTinHat/maskmyxyz/master)
![License](https://img.shields.io/github/license/TheTinHat/MaskMyPy)
[![PyPi](https://img.shields.io/pypi/v/maskmypy)](https://pypi.org/project/maskmypy/)

# Introduction

[MaskMyPy](https://github.com/TheTinHat/MaskMyPy) is a Python package that performs geographic masking on [GeoDataFrames](http://geopandas.org/data_structures.html). It offers two main methods: [donut masking](donut.md) and [street masking](street.md).


MaskMyPy also supports calculating metrics to help optimize and validate masking parameters. Currently, it offers k-anonymity estimation using population data, k-anonymity calculation using address data, and displacement distance calculation between sensitive and masked points.

**Disclaimer**: *MaskMyPy is offered as-is, without warranty of any kind. Geographic masking is a hard problem that requires informed decisions and validation. MaskMyPy provides helpful tools for geographic masking, but does not replace expertise.*

## Installation

```
pip install maskmypy
```

## Example

The following snippet applies a 500 meter* donut mask to a GeoDataFrame of sensitive points:

```python
>>> from maskmypy import Donut
>>> import geopandas as gpd
>>> sensitive_points = gpd.read_file('sensitive_points')
>>> sensitive_points
     CID                           geometry
0      1  POINT (-13703523.337 6313860.932)
1      2  POINT (-13703436.959 6314112.457)
2      3  POINT (-13703679.041 6314040.923)
3      4  POINT (-13703285.553 6313721.356)
4      5  POINT (-13703200.338 6313847.431)

>>> masked_points = Donut(sensitive_points, max_distance=500).run()
>>> masked_points
     CID                           geometry
0      1  POINT (-13703383.941 6313989.161)
1      2  POINT (-13703227.863 6313973.121)
2      3  POINT (-13703313.001 6314172.582)
3      4  POINT (-13703107.232 6313614.978)
4      5  POINT (-13702837.385 6314140.874)
```

We can also calculate the distance that each points was displaced by adding the `displacement=True` flag to `.run()`:

```python
masked_points = Donut(points).run(displacement=True)
masked_points
     CID                           geometry   _distance
0      1  POINT (-13703383.941 6313989.161)  189.404946
1      2  POINT (-13703227.863 6313973.121)  251.267943
2      3  POINT (-13703313.001 6314172.582)  388.997713
3      4  POINT (-13703107.232 6313614.978)  207.639785
4      5  POINT (-13702837.385 6314140.874)  466.738146
```

\* *Note that the `max_distance` parameter assumes that the supplied distance is in the same unit as the GeoDataFrame. For example, if your GeoDataFrame is projected to a CRS that uses feet, then `max_distance=500` will displace points up to 500 feet.*

## Roadmap
The following features are currently planned:

- Location Swapping/Verified Neighbor masks
- Automatic plotting of point displacement
- The ability to save mask metadata
