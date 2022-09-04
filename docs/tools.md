---
title: Evaluation Tools
---


**Warning**: Do not release datasets containing displacement distances or k-anonymity values. These are only to assist the person masking the data. Releasing such values may compromise privacy and aid attackers seeking to re-identify point locations. Always remove these columns before sharing the data.

## K-Anonymity
Maskmypy is able to calculate the k-anonymity of each point after masking. Two methods are available for this: [`estimate_k`](#maskmypy.tools.estimate_k) and [`calculate_k`](#maskmypy.tools.calculate_k). Estimates of k-anonymity are inferred from population data, and assume a homogeneously distributed population within each population (i.e. census) polygon. Address-based k-anonymity is more accurate and uses actual address data to calculate k-anonymity.

<div class="func-heading">maskmypy.tools.estimate_k(secret, mask, population)</div>
::: maskmypy.tools.estimate_k
---

<div class="func-heading">maskmypy.tools.calculate_k(secret, mask, address)</div>
::: maskmypy.tools.calculate_k


## Displacement Distance
Displacement distance refers to the distance that each point is moved from its original location during anonymization. They are helpful insofar as they allow you to assess how much your data has been distorted by the masking process, both in terms of too much or too little. For instance, you may find that one point was only moved 6 meters, which doesn't protect privacy much at all. Alternatively, you may find that some points were displaced too far, say 6000 meters. MaskMyPy can easily calculate the displacement distance of masked data as well as generate a quick map of displacement distances to help you visually inspect the anonymization results.

<div class="func-heading">maskmypy.tools.displacement(secret, mask)</div>
::: maskmypy.tools.displacement
---

<div class="func-heading">maskmypy.tools.map_displacement(secret, mask)</div>
::: maskmypy.tools.map_displacement
---

## Shortcut: Evaluation Using `.run()`
For convenience, several evaluation tools can be quickly executed by adding flags to the `.run()` method of each masking class. Here is the docstring for `.run()`:

---

::: maskmypy.mask.Mask.run
    options:
      heading_level: 0
---
