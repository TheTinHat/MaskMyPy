from maskmypy import Donut


def test_random_seed(points):
    Donut(points, 10, 100).run()

    parameters = Donut(points, 10, 100, seed=123456).params
    assert parameters["seed"] == 123456
    assert isinstance(parameters["seed"], int)


def test_container(points, container):
    Donut(points, 10, 100, container=container).run()
