from geopandas import GeoDataFrame, GeoSeries
from shapely import Geometry
from shapely.ops import unary_union


def unify(gs: GeoSeries) -> Geometry:
    geometries = gs.tolist()
    union = unary_union(geometries)
    return union


def unify_by_label(
    gdf: GeoDataFrame,
    label_name: str,
) -> GeoDataFrame:
    union_gdf = gdf.groupby(label_name).agg({"geometry": unify})
    union_gdf = union_gdf.reset_index()
    union_gdf = union_gdf.set_geometry("geometry")
    return union_gdf
