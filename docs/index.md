<div style="text-align:center;"><img src="assets/logo.png" style="max-width: 400px;"></div>

-----
Python tools for anonymizing geographic data.

![Master Tests](https://img.shields.io/github/checks-status/TheTinHat/maskmyxyz/master)
![License](https://img.shields.io/github/license/TheTinHat/MaskMyPy)
![PyPi](https://img.shields.io/pypi/v/maskmypy)
# Introduction

[MaskMyPy](https://github.com/TheTinHat/MaskMyPy) is a Python package that performs geographic masking on [GeoDataFrames](http://geopandas.org/data_structures.html). It offers two main methods: [donut masking](donut.md) and [street masking](street.md).


MaskMyPy also supports calculating metrics to help optimize and validate masking parameters. Currently, it offers k-anonymity estimation using population data, k-anonymity calculation using address data, and displacement distance calculation between sensitive and masked points.

**Disclaimer**: *MaskMyPy is offered as-is, without warranty of any kind. Geographic masking is a hard problem that requires informed decisions and validation. MaskMyPy provides helpful tools for geographic masking, but does not replace expertise.*

## Installation
```
pip install maskmypy
```

## Roadmap
The following features are currently planned:
- Location Swapping/Verified Neighbor masks
- Automatic plotting of point displacement
- The ability to save mask metadata

<style>
.md-content__inner > h1:first-child  {
  display: none;
}
</style>