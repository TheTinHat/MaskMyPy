import click
import geopandas as gpd

from .donut import Donut
from .street import Street


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
    help="Distance to add around edges of secret points before clipping context layers. Default: one fifth the extent of secret points.",
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
    help="The minimum number of nodes to traverse along the street network. Default: 18.",
)
@click.option(
    "--max-depth",
    type=click.INT,
    help="The maximum number of nodes to traverse along the street network. Default: 20.",
)
@click.option(
    "--max-length",
    type=click.FLOAT,
    help="When initially locating each point on the street network, MaskMyPy verifies that the nearest node is connected to the network and has neighbors that are no more than `max_length` away (in meters). If not, the next closest point is selected and checked the same way. This acts as a sanity check to prevent extremely large masking distances, such as might be caused by highways. Default: `500`.",
)
@click.option(
    "--padding",
    type=click.FLOAT,
    help="Distance to add around edges of secret points before clipping context layers. Default: one fifth the extent of secret points.",
)
@click.option(
    "--seed",
    type=click.INT,
    help="Used to seed the random number generator so that masks are reproducible. In other words, given a certain seed, MaskMyPy will always mask data the exact same way. If left unspecified, a seed is randomly selected using SystemRandom",
)
def street(secret_input, masked_output, **kwargs):
    pruned_kwargs = {k: v for k, v in kwargs.items() if v}
    Street(gpd.read_file(secret_input), **pruned_kwargs).run().to_file(masked_output)
