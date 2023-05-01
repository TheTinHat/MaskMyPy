import pytest
from pandas.testing import assert_frame_equal

from maskmypy import Street


@pytest.mark.slow
def test_random_seed(points):
    points = points[0:5]
    candidate_1 = Street(points, 2, 5, seed=12345).run()
    candidate_2 = Street(points, 2, 5, seed=12345).run()
    candidate_3 = Street(points, 2, 5, seed=98765).run()

    assert_frame_equal(candidate_1, candidate_2)

    with pytest.raises(AssertionError):
        assert_frame_equal(candidate_1, candidate_3)


# def test_street(points):
#     candidate_0 = Street(points, 15, 20, seed=12345).run()
