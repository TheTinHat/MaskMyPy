import os
import shutil

import geopandas as gpd
import pytest

from maskmypy import Atlas, Candidate, Donut

from .fixtures import atlas, points, tmpdir, container


def test_random_seed(points):
    mdf = Donut(points, 10, 100).run()

    parameters = Donut(points, 10, 100, seed=123456).params
    assert parameters["seed"] == 123456
    assert isinstance(parameters["seed"], int)


def test_container(points, container):
    mdf = Donut(points, 10, 100, container=container).run()
