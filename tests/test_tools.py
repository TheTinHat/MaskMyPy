import osmnx
import pytest

from maskmypy import tools


def test_atlas_mask_snap(points_small):
    unsnapped = points_small
    snapped = tools.snap_to_streets(points_small)

    with pytest.raises(osmnx._errors.InsufficientResponseError):
        unsnapped_point = unsnapped.to_crs(epsg=4326).iloc[0].geometry
        osmnx.features.features_from_point(
            (unsnapped_point.y, unsnapped_point.x), tags={"highway": True}, dist=2
        )

    snapped_point = snapped.to_crs(epsg=4326).iloc[0].geometry
    osmnx.features.features_from_point(
        (snapped_point.y, snapped_point.x), tags={"highway": True}, dist=2
    )
    assert snapped.crs == unsnapped.crs
    assert snapped.iloc[0].geometry != unsnapped.iloc[0].geometry


def test_unmasked_points(points):
    masked = points.copy()
    i = 5

    masked.loc[i:, "geometry"] = masked.loc[i:, masked.geometry.name].translate(1, 0, 0)
    with pytest.warns(UserWarning):
        masked = tools._mark_unmasked_points(points, masked)

    assert all(masked.loc[i:, "UNMASKED"] == 0)
    assert all(masked.loc[: i - 1, "UNMASKED"] == 1)
    assert masked["UNMASKED"].sum() == i
