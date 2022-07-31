import maskmypy
import click


@click.group()
def cli():
    pass


@click.command(help="Perform donut masking on a given shapefile")
@click.argument("shapefile_path", type=click.Path(exists=True))
@click.argument("output_path", type=click.Path(dir_okay=False))
@click.option(
    "--population",
    type=click.Path(exists=True),
    help="Path to shapefile containing population polygons.",
)
@click.option(
    "--popcolumn",
    type=click.STRING,
    help="Name of the population column in the population polygons.",
)
@click.option(
    "--popmultiplier",
    type=click.INT,
    help="Multiplier value to be used when using population to scale masking distances.",
)
@click.option(
    "--distance",
    type=click.FLOAT,
    help="The maximum distance that points should be displaced.",
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
    "--addresses",
    type=click.Path(exists=True),
    help="Path to shapefile containing address points.",
)
@click.option("--max-k", type=click.INT, help="")
@click.option("--tries", type=click.INT, help="")
@click.option("--seed", type=click.INT, help="")
@click.option("--displacement", is_flag=True, help="")
@click.option("--estimate-k", is_flag=True, help="")
@click.option("--calculate-k", is_flag=True, help="")
def donut(
    shapefile_path,
    output_path,
    popcolumn,
    population,
    popmultiplier,
    tries,
    distance,
    seed,
    ratio,
    distribution,
    container,
    addresses,
    max_k,
    displacement,
    estimate_k,
    calculate_k,
):
    pass


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