---
title: Atlas
---

## Introduction 

The structure of a candidate is as follows:
```python
{
  mask: str, # Name of the mask callable used to create the candidate
  kwargs: dict, # Dictionary containing the keyword arguments used to create the candidate
  checksum: str, # Checksum of the candidate GeoDataFrame
  timestamp: float,
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

## Reference
::: maskmypy.Atlas
    options:  
      show_root_heading: false
      show_root_toc_entry: false
      show_root_members_full_path: false
