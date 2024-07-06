---
title: Atlas
---

## Introduction
The `Atlas()` class makes it easy to both mask datasets and evaluate new masks. It acts as a type of manager that allows you to quickly test any number of combinations of masks and their associated parameters, automatically performing the evaluation for you and keeping track of the results. 


## Candidates
When the Atlas executes a given mask, the result is referred to as a 'candidate'. Each candidate is a simple Python dictionary stored in a ordinary list at `Atlas.candidates[]`. You can also access the candidate list by slicing the Atlas itself, e.g. `Atlas[2]`

The structure of a candidate is as follows:

```python
{
  mask: str, # Name of the mask callable used to create the candidate
  kwargs: dict, # Dictionary containing the keyword arguments used to create the candidate
  checksum: str, # Checksum of the candidate GeoDataFrame
  stats: { # Dictionary containing statistics describing information loss and privacy protection
    "central_drift": float,
    "displacement_min": float,
    "displacement_max": float,
    "displacement_med": float,
    "displacement_mean": float,
    "nnd_min_delta": float,
    "nnd_max_delta": float,
    "nnd_mean_delta": float,
    "ripley_rmse": float,
    "k_min": int,
    "k_max": int,
    "k_med": float,
    "k_mean": float,
    "k_satisfaction_5": float,
    "k_satisfaction_25": float,
    "k_satisfaction_50": float,
  },
}
```

## Using Custom Masks
The Atlas can utilize custom masking functions passed to `Atlas.mask()` so long as they meet the following requirements: 

 - The first argument is a GeoDataFrame of sensitive points,
 - They return a masked GeoDataFrame in the same CRS as the input,
 - All other arguments are specified as keyword arguments (kwargs),
 - When a `seed` argument is provided, outputs are reproducible.

## Reference

::: maskmypy.Atlas
