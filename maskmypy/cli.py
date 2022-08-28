import click
import geopandas as gpd

from .donut import Donut
from .street import Street
from .tools import map_displacement, estimate_k, calculate_k


@click.group()
def cli():
    pass


@cli.command(help="Perform donut masking on a given shapefile")
@click.argument("secret_input", type=click.Path(exists=True))
@click.argument("masked_output", type=click.Path(dir_okay=False))
@click.option(
    "--min-distance",
    type=click.FLOAT,
    help="The minimum distance that points should be displaced.",
)
@click.option(
    "--max-distance",
    type=click.FLOAT,
    help="The maximum distance that points should be displaced.",
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
    "--population",
    type=click.Path(exists=True),
    help="Path to shapefile containing population polygons.",
)
@click.option(
    "--pop-col",
    type=click.STRING,
    help="Name of the population column in the population polygons.",
)
@click.option(
    "--max-tries",
    type=click.INT,
    help="Limits the number of attempts to mask points within containment layer.",
)
@click.option(
    "--padding",
    type=click.FLOAT,
    help="Distance to add around edges of secret points before clipping supplementary layers. Default: one fifth the extent of secret points.",
)
@click.option(
    "--seed",
    type=click.INT,
    help="If specified, ensures that masks are reproducible such that a given seed always returns the same mask reuslt.",
)
def donut(secret_input, masked_output, **kwargs):
    pruned_kwargs = {k: v for k, v in kwargs.items() if v}
    Donut(gpd.read_file(secret_input), **pruned_kwargs).run().to_file(masked_output)


@cli.command(help="Perform street masking on a given shapefile")
@click.argument("secret_input", type=click.Path(exists=True))
@click.argument("masked_output", type=click.Path(dir_okay=False))
@click.option(
    "--min-depth",
    type=click.INT,
    help="",
)
@click.option(
    "--max-depth",
    type=click.INT,
    help="",
)
@click.option(
    "--max-length",
    type=click.FLOAT,
    help="Measured in meters only. Streets longer than this distance will be ignored when analyzing the road network. Prevents very long street segments (e.g. highways) from exaggerating masking distances.",
)
@click.option(
    "--padding",
    type=click.FLOAT,
    help="Distance to add around edges of secret points before clipping supplementary layers. Default: one fifth the extent of secret points.",
)
@click.option(
    "--seed",
    type=click.INT,
    help="If specified, ensures that masks are reproducible such that a given seed always returns the same masked result.",
)
def street(secret_input, masked_output, **kwargs):
    pruned_kwargs = {k: v for k, v in kwargs.items() if v}
    Street(gpd.read_file(secret_input), **pruned_kwargs).run().to_file(masked_output)
