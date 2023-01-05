def validate_input(**kwargs):
    if kwargs.get("sensitive_gdf") is not None:
        crs = kwargs["sensitive_gdf"].crs
        assert_geom_type(kwargs["sensitive_gdf"], "Point")

    if kwargs.get("min") or kwargs.get("max"):
        assert kwargs["max"] > kwargs["min"]

    if kwargs.get("container") is not None:
        assert kwargs["container"].crs == crs
        assert_geom_type(kwargs["container"], "Polygon", "MultiPolygon")

    return True


def assert_geom_type(gdf, *type_as_string):
    geom_types = [True if geom_type in type_as_string else False for geom_type in gdf.geom_type]
    assert all(geom_types)
    return True