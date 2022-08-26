---
title: Donut Masking
---

## Donut Masking

Donut masking

**Usage:**
To perform basic donut geomasking on a geodataframe containing sensitive points, with a maximum displacement distance of 500 meters and an minimum displacement distance of 20% of the maximum distance (i.e. 100 meters), the code would look like this:

```python
from maskmypy import Donut

donutmask = Donut(
    sensitive=sensitive, # Name of the sensitive geodataframe
    max_distance=500, # The maximum possible distance that points are displaced
    ratio=0.2, # The ratio used to define the minimum distance points are displaced
    distribution='uniform', # The distribution to use when displacing points. Other options include 'gaussian' and 'areal'. 'Areal' distribution means points are more likely to be displaced further within the range.
    container=container) # Optional, a geodataframe used to ensure that points do not leave a particular area.

donutmask.run()

masked = donutmask.mask
```

To perform full donut geomasking (i.e. using census data and a target k-anonymity range rather than distance range) with a maximum k-anonymity of 1000 and minimum of 200, and a census geodataframe called population, the code would appear as follows:

```python
from maskmypy import Donut_K

donutmask = Donut_K(
    sensitive, # Name of the sensitive geodataframe
    population=population, # Name of the census geodataframe
    pop_col='pop', # Name of the column containing the population field
    max_k_anonymity=1000, # The maximum possible k-anonymity value
    ratio=0.2, # The ratio used to define the minimum possible k-anonymity value.
    distribution='uniform', # The distribution to use when displacing points. Other options include 'gaussian' and 'areal'. 'Areal' distribution means points are more likely to be displaced further within the range.
    container=container) # Optional, a geodataframe used to ensure that points do not leave a particular area.

donutmask.run()

masked = donutmask.mask
```
