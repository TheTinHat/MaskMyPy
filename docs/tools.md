---
title: Tools
---


## K-Anonymity
Maskmypy is able to calculate the k-anonymity of each point after masking. Two methods are available for this: estimates, and exact calculations. Estimates of k-anoynmity are inferred from census data, and assume a homogeneously distributed population within each census polygon. Address-based k-anonymity is more accurate and uses actual home address data to calculate k-anonymity.

### Estimate K-Anonymity
**Usage:**
After the data has been masked, estimating k-anoynmity using census data would look like this and will add a column to the masked geodataframe:

```python
mask.estimate_k(
    population=population, # Name of the census geodataframe. Not necessary if you already included this parameter in the original masking steps.
    pop_col='pop') # Name of the column containing the population field. Not necessary if you already included this parameter in the original masking steps.
```

### Calculate K-Anonymity
**Usage:**
After the data has been masked, calcualting address-based k-anoynmity would look like this and will add a column to the masked geodataframe:

```python
mask.calculate_k(address='') # Name of the geodataframe including address points.
```

## Displacement Distance
**Usage:**
To add a column to the masked geodataframe that includes the actual displacement distances (in meters), one can just run:

```python
mask.displacement()
```


### tools.displacement()
::: maskmypy.tools.displacement