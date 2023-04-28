import click
import geopandas as gpd
from pathlib import Path
from . import masks
from .atlas import Atlas
from . import tools

# @click.option(
#     "",
#     type=click.FLOAT,
#     help="",
# )


@click.group()
def cli():
    """
    MaskMyPy contains tools for anonymizing sensitive point data using techniques
    known as geographic masks. It also contains tools for analyzing the level of
    privacy provided by a given geographically masked dataset, as well as the
    amount of information lost during the process.

    Examples:\n
        $ maskmypy mask donut --min 50 --max 500  points.shp masked_points.shp\n
        Applies donut masking with a minimum distance of 50 meters and maximum
        distance of 500 meters to points.shp and saves the result as masked_points.shp

        $ maskmypy analyst estimate_k --sensitive points.shp --masked masked.shp
         --population addresses.shp --output estimated_k.shp\n
        Uses an address point layer to estimate the k-anonymity achieved by
        masked_points.shp.
    """
    pass


@cli.group(help="Command group containing geographic masking tools.")
def mask():
    pass


@mask.command(help="Perform donut masking on a set of points")
@click.option(
    "--input", type=click.Path(dir_okay=False, exists=True, path_type=Path), help="", required=True
)
@click.option("--output", type=click.Path(dir_okay=False, path_type=Path), help="", required=True)
@click.option("--min", type=click.FLOAT, help="", required=True)
@click.option("--max", type=click.FLOAT, help="", required=True)
@click.option("--inlayer", type=click.STRING, help="Name of layer if input is a GeoPackage.")
@click.option("--outlayer", type=click.STRING, help="Name of layer if output is a GeoPackage.")
@click.option(
    "--test",
    type=click.FLOAT,
    help="",
)
@click.option(
    "--seed",
    type=click.INT,
    help="Used to seed the random number generator so that masks are reproducible.",
)
def donut(input, output, **kwargs):
    kwargs = {k: v for k, v in kwargs.items() if v}
    if "inlayer" in kwargs:
        sensitive = gpd.read_file(input, layer=kwargs["inlayer"], driver="GPKG")
    else:
        sensitive = gpd.read_file(input)

    masked = masks.Donut(sensitive, **kwargs).run()

    if "outlayer" in kwargs:
        masked.to_file(output, layer=kwargs["outlayer"], driver="GPKG")
    else:
        masked.to_file(output)


@cli.group(help="Subcommand containing analysis tools.")
def analyst():
    pass


@cli.group(help=".")
def atlas():
    pass
