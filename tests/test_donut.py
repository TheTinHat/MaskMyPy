import os
import shutil

import geopandas as gpd
import pytest

from maskmypy import Atlas, Candidate, Donut

from .fixtures import atlas, points, tmpdir, container


def test_random_seed(points):
    mdf, parameters = Donut(points, 10, 100).run()
    assert isinstance(parameters["seed"], int)

    mdf, parameters = Donut(points, 10, 100, seed=123456).run()
    assert parameters["seed"] == 123456


def test_container(points, container):
    mdf, parameters = Donut(points, 10, 100, container=container).run()
