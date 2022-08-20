## Street Masking
Street masking automatically downloads OpenStreetMap road network data and uses it to geographically mask your sensitive points. It works by first downloading the road network data, snapping each sensitive point to the nearest node on the network (an intersection or dead end), and then calculating the average network-distance between that node and a pool of the closest x number of nodes (e.g. the closest 20 nodes on the network, known as the search depth). This average distance is the target displacement distance. Finally, it selects a node from the pool whose network-distance from the starting node is closest to the target displacement distance.

**Usage:** To street mask a geodataframe containing sensitive points with a search-depth value of 20, the code would be as follows:

```
from maskmypy import Street

streetmask = Street(
    sensitive, # Name of the sensitive geodataframe
    depth=20, # The search depth value used to calculate displacement distances.
    padding=2000, # Used to download road network data surrounding the study area. Needs to be sufficiently large to reduce edge effects. Increasing reduces edge effects, but uses more memory.
    max_length=500) # Optional, but recommended that you read below for full explanation of what this does.


streetmask.run() # Single threaded by default. Add `parallel=True` as parameter to run on all CPU cores, drastically increasing performance.

masked = streetmask.mask
```

**About max_length**: when snapping points to the street network, the algorithm checks to make sure that the nearest node is actually connected to the network and has neighbors that are no more than max_length away (in meters). If it does not, then the next closest viable node is selected, checked, and so on. This acts as a sanity check to prevent extremely large masking distances. Feel free to change this to whatever you feel is appropriate.
