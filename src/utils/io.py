# https://github.com/geopandas/dask-geopandas/issues/16
import dask
from dask.delayed import delayed, tokenize


@delayed
def _extra_deps(func, *args, extras=None, **kwargs):
    return func(*args, **kwargs)


def to_file(df, path, driver="GPKG", parallel=False, compute=True, **kwargs):
    """
    Write to single file.

    Parameters
    ----------
    df : dask_geopandas.GeoDataFrame
    path : str
        Filename.
    parallel : bool, default False
        When true, have each block append itself to the DB table concurrently.
        This can result in DB rows being in a different order than the source
        DataFrame's corresponding rows. When false, load each block into the
        SQL DB in sequence.
    compute : bool, default True
        When true, call dask.compute and perform the load into SQL; otherwise,
        return a Dask object (or array of per-block objects when parallel=True)
    """
    # based on dask.dataframe's to_sql
    def make_meta(meta):
        return meta.to_file(path, driver=driver, mode="w", **kwargs)

    make_meta = delayed(make_meta)
    meta_task = make_meta(df._meta)

    worker_kwargs = dict(kwargs, driver=driver, mode="a")

    if parallel:
        result = [
            _extra_deps(
                d.to_file,
                path,
                extras=meta_task,
                **worker_kwargs,
                dask_key_name="to_file-%s" % tokenize(d, **worker_kwargs)
            )
            for d in df.to_delayed()
        ]
    else:
        result = []
        last = meta_task
        for d in df.to_delayed():
            result.append(
                _extra_deps(
                    d.to_file,
                    path,
                    extras=last,
                    **worker_kwargs,
                    dask_key_name="to_file-%s" % tokenize(d, **worker_kwargs)
                )
            )
            last = result[-1]
    result = delayed(result)

    if compute:
        dask.compute(result, scheduler="processes")
    else:
        return result
