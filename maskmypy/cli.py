import click
import geopandas as gpd

from .donut import Donut
from .street import Street


@click.group()
def cli():
    pass


@cli.command(help="Perform donut masking on a given shapefile")
@click.argument("input_shp", type=click.Path(exists=True))
@click.argument("output_shp", type=click.Path(dir_okay=False))
@click.option(
    "--max-distance",
    type=click.FLOAT,
    help="The maximum distance that points should be displaced.",
)
@click.option(
    "--population",
    type=click.Path(exists=True),
    help="Path to shapefile containing population polygons.",
)
@click.option(
    "--population-column",
    type=click.STRING,
    help="Name of the population column in the population polygons.",
)
@click.option(
    "--ratio",
    type=click.FLOAT,
    help="The ratio of the max displacement distance used to define the minimum displacement distance (e.g. if distance=100 and ratio=0.1, then the minimum distance will be set to 10).",
)
@click.option(
    "--distribution",
    type=click.STRING,
    help="The distribution used to randomly displace points. Can be 'uniform', 'areal', or 'gaussian'.",
)
@click.option(
    "--container",
    type=click.Path(exists=True),
    help="Path to shapefile containing polygons in which displaced points must be contained.",
)
@click.option(
    "--address-points",
    type=click.Path(exists=True),
    help="Path to shapefile containing address points.",
)
@click.option("--max-tries", type=click.INT, help="")
@click.option("--seed", type=click.INT, help="")
def donut(input_shp, output_shp, **kwargs):
    pruned_kwargs = {k: v for k, v in kwargs.items() if v}
    donutmask = Donut(gpd.read_file(input_shp), **pruned_kwargs)
    donutmask.run()
    donutmask.mask.to_file(output_shp)
