import click
import geopandas as gpd

import maskmypy


@click.group()
def cli():
    pass


@cli.command(help="Perform donut masking on a given shapefile")
@cli.argument("input_shp", type=click.Path(exists=True))
@cli.argument("output_shp", type=click.Path(dir_okay=False))
@cli.option(
    "--population",
    type=click.Path(exists=True),
    help="Path to shapefile containing population polygons.",
)
@cli.option(
    "--pop-column",
    type=click.STRING,
    help="Name of the population column in the population polygons.",
)
@cli.option(
    "--distance",
    type=click.FLOAT,
    help="The maximum distance that points should be displaced.",
)
@cli.option(
    "--ratio",
    type=click.FLOAT,
    help="The ratio of the max displacement distance used to define the minimum displacement distance (e.g. if distance=100 and ratio=0.1, then the minimum distance will be set to 10).",
)
@cli.option(
    "--distribution",
    type=click.STRING,
    help="The distribution used to randomly displace points. Can be 'uniform', 'areal', or 'gaussian'.",
)
@cli.option(
    "--container",
    type=click.Path(exists=True),
    help="Path to shapefile containing polygons in which displaced points must be contained.",
)
@cli.option(
    "--addresses",
    type=click.Path(exists=True),
    help="Path to shapefile containing address points.",
)
@cli.option("--max-k", type=click.INT, help="")
@cli.option("--tries", type=click.INT, help="")
@cli.option("--seed", type=click.INT, help="")
@cli.option("--displacement-distance", is_flag=True, help="")
@cli.option("--estimate-k", is_flag=True, help="")
@cli.option("--calculate-k", is_flag=True, help="")
def donut(input_shp, output_shp, **kwargs):
    donutmask = maskmypy.Donut(gpd.read_file(shapefile_path), **kwargs)
    donutmask.execute()
    donutmask.masked.to_file(output_path)


@click.command(help="Perform street masking on a given shapefile")
@click.argument("output_path", type=click.Path(dir_okay=False))
@click.option("--depth", type=click.INT, help="")
@click.option("--add-extent", type=click.FLOAT, help="")
@click.option("--max-street-length", type=click.FLOAT, help="")
@click.option("--population", type=click.Path(exists=True), help="")
@click.option("--popcolumn", type=click.STRING, help="")
@click.option("--addresses", type=click.Path(exists=True), help="")
@click.option("--displacement", is_flag=True, help="")
@click.option("--estimate-k", is_flag=True, help="")
@click.option("--calculate-k", is_flag=True, help="")
def street():
    pass


@click.command(
    help="Calculate displacement distance and privacy metrics given a pair of sensitive and masked shapefiles"
)
@click.option("--input", type=click.Path(exists=True), help="")
@click.option("--masked", type=click.Path(exists=True), help="")
@click.option("--population", type=click.Path(exists=True), help="")
@click.option("--popcolumn", type=click.STRING, help="")
@click.option("--addresses", type=click.Path(exists=True), help="")
def analyze():
    pass


cli.add_command(donut)
cli.add_command(street)
cli.add_command(analyze)
