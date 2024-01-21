import glob
import os
import re
from typing import Dict, Iterator, Tuple, Union

import numpy as np
import geopandas as gpd

from .config import Config, Store
from .types import TileParameters, TileData, StepParameters, PipelineParameters


class TileStore:
    def __init__(
        self,
        config: Config,
        pipeline_parameters: PipelineParameters
    ) -> None:
        self.config = config
        self.pipeline_parameters = pipeline_parameters

    def has_tile(
        self,
        step_parameters: StepParameters,
        tile_parameters: TileParameters,
    ) -> bool:
        return True

    def get_tile(
        self,
        step_parameters: StepParameters,
        tile_parameters: TileParameters,
    ) -> TileData:
        pass

    def get_region(
        self,
        step_parameters: StepParameters,
        region_parameters: TileParameters,
    ) -> TileData:
        if step_parameters.data_type != np.ndarray:
            raise Exception(
                "`get_region` currenly only works "
                "on tile data type `np.ndarray`."
            )

        pp = self.pipeline_parameters

        data = np.zeros(
            (region_parameters.width, region_parameters.height)
        )
        region_start_x = region_parameters.start_x
        region_start_y = region_parameters.start_y
        region_end_x = region_parameters.start_x + region_parameters.width
        region_end_y = region_parameters.start_y + region_parameters.height

        for start_x in range(0, pp.width, pp.tile_size):
            if start_x + pp.tile_size < region_start_x:
                continue
            if start_x >= region_end_x:
                break

            for start_y in range(0, pp.height, pp.tile_size):
                if start_y + pp.tile_size < region_start_y:
                    continue
                if start_y >= region_end_y:
                    break

                tile_parameters = TileParameters(
                    start_x=start_x,
                    start_y=start_y,
                    width=pp.tile_size,
                    height=pp.tile_size,
                )
                tile = self.get_tile(step_parameters, tile_parameters)

                tile_width = tile.shape[0]
                tile_height = tile.shape[1]
                end_x = start_x + tile_width
                end_y = start_y + tile_height

                if start_x < region_start_x:
                    rel_tile_start_x = region_start_x - start_x
                    rel_data_start_x = 0
                else:
                    rel_tile_start_x = 0
                    rel_data_start_x = start_x - region_start_x
                if end_x < region_end_x:
                    rel_tile_end_x = end_x - start_x
                    rel_data_end_x = end_x - region_start_x
                else:
                    rel_tile_end_x = region_end_x - start_x
                    rel_data_end_x = region_end_x - region_start_x
                    pass
                if start_y < region_start_y:
                    rel_tile_start_y = region_start_y - start_y
                    rel_data_start_y = 0
                else:
                    rel_tile_start_y = 0
                    rel_data_start_y = start_y - region_start_y
                if end_y < region_end_y:
                    rel_tile_end_y = end_y - start_y
                    rel_data_end_y = end_y - region_start_y
                else:
                    rel_tile_end_y = region_end_y - start_y
                    rel_data_end_y = region_end_y - region_start_y

                data[
                    rel_data_start_x:rel_data_end_x,
                    rel_data_start_y:rel_data_end_y
                ] = tile[
                    rel_tile_start_x:rel_tile_end_x,
                    rel_tile_start_y:rel_tile_end_y,
                ]

        return data

    # Yield tiles one at a time so don't store them all in memory.
    def get_all_tiles(
        self,
        step_parameters: StepParameters,
    ) -> Iterator[Tuple[TileParameters, TileData]]:
        yield (TileParameters(0, 0, 0, 0), np.array([]))

    def save_tile(
        self,
        step_parameters: StepParameters,
        tile_parameters: TileParameters,
        tile: TileData,
    ) -> None:
        pass


class TileMemory(TileStore):
    def __init__(
        self,
        config: Config,
        pipeline_parameters: PipelineParameters,
    ) -> None:
        if config.store != Store.Memory:
            raise Exception(
                f"Storage configuration {config.store} is not memory."
            )

        super().__init__(
            config,
            pipeline_parameters,
        )

        self.all_step_tiles: Dict[
            StepParameters,
            Dict[TileParameters, TileData]
        ] = {}

    def has_tile(
        self,
        step_parameters: StepParameters,
        tile_parameters: TileParameters,
    ) -> bool:
        if step_parameters not in self.all_step_tiles:
            return False
        step_map = self.all_step_tiles[step_parameters]
        if tile_parameters not in step_map:
            return False
        return True

    def get_tile(
        self,
        step_parameters: StepParameters,
        tile_parameters: TileParameters,
    ) -> Union[TileData, None]:
        if step_parameters not in self.all_step_tiles:
            return None
        step_map = self.all_step_tiles[step_parameters]
        if tile_parameters not in step_map:
            return None
        return step_map[tile_parameters]

    def get_all_tiles(
        self,
        step_parameters: StepParameters,
    ) -> Iterator[Tuple[TileParameters, TileData]]:
        if step_parameters not in self.all_step_tiles:
            return
        step_map = self.all_step_tiles[step_parameters]
        for tile_parameters, tile in step_map.items():
            yield (tile_parameters, tile)

    def save_tile(
        self,
        step_parameters: StepParameters,
        tile_parameters: TileParameters,
        tile: TileData,
    ) -> None:
        if step_parameters not in self.all_step_tiles:
            self.all_step_tiles[step_parameters] = {}
        step_map = self.all_step_tiles[step_parameters]
        step_map[tile_parameters] = tile


class TileDisk(TileStore):
    def __init__(
        self,
        config: Config,
        pipeline_parameters: PipelineParameters,
    ) -> None:
        if config.store != Store.Disk:
            raise Exception(
                f"Storage configuration {config.store} is not disk."
            )

        super().__init__(
            config,
            pipeline_parameters,
        )
        pass

    def _get_tile_params_from_file(
        self,
        step_parameters: StepParameters,
        filepath: str,
    ) -> Union[TileParameters, None]:
        pattern = f"{step_parameters.name}" \
                  "-tile_(?P<start_x>[0-9]*)-(?P<start_y>[0-9]*)" \
                  "_(?P<width>[0-9]*)-(?P<height>[0-9]*)"
        match = re.search(pattern, filepath)
        if match is None:
            return None

        start_x = int(match.group('start_x'))
        start_y = int(match.group('start_y'))
        width = int(match.group('width'))
        height = int(match.group('height'))
        return TileParameters(
            start_x=start_x,
            start_y=start_y,
            width=width,
            height=height,
        )

    def _get_file_extension(
        self,
        step_parameters: StepParameters,
    ) -> str:
        if step_parameters.data_type == np.ndarray:
            return "npy"
        elif step_parameters.data_type == gpd.GeoDataFrame:
            return "gpkg"
        else:
            raise Exception(
                f"Unsupported data type: {str(step_parameters.data_type)}"
            )

    def _get_tile_path(
        self,
        step_parameters: StepParameters,
        tile_parameters: TileParameters,
    ) -> str:
        return os.path.join(
            self.config.disk_config.work_dir,
            f"{step_parameters.name}-tile"
            f"_{tile_parameters.start_x}-{tile_parameters.start_y}"
            f"_{tile_parameters.width}-{tile_parameters.height}"
            f".{self._get_file_extension(step_parameters)}",
        )

    def _load_tile(
        self,
        step_parameters: StepParameters,
        tile_path: str,
    ) -> Union[TileData, None]:
        if not os.path.isfile(tile_path):
            return None

        if step_parameters.data_type == np.ndarray:
            tile = np.load(tile_path)
        elif step_parameters.data_type == gpd.GeoDataFrame:
            tile = gpd.read_file(tile_path)
        else:
            raise Exception(
                f"Unsupported data type: {str(step_parameters.data_type)}"
            )
        return tile

    def has_tile(
        self,
        step_parameters: StepParameters,
        tile_parameters: TileParameters,
    ) -> bool:
        tile_path = self._get_tile_path(step_parameters, tile_parameters)
        return os.path.isfile(tile_path)

    def get_tile(
        self,
        step_parameters: StepParameters,
        tile_parameters: TileParameters,
    ) -> Union[TileData, None]:
        tile_path = self._get_tile_path(step_parameters, tile_parameters)
        return self._load_tile(step_parameters, tile_path)

    def get_all_tiles(
        self,
        step_parameters: StepParameters,
    ) -> Iterator[Tuple[TileParameters, TileData]]:
        pattern = os.path.join(
            self.config.disk_config.work_dir,
            f"{step_parameters.name}-tile_*_*"
            f".{self._get_file_extension(step_parameters)}",
        )
        for tile_path in glob.glob(pattern):
            tile_parameters = self._get_tile_params_from_file(
                step_parameters,
                tile_path
            )
            assert tile_parameters is not None
            tile = self._load_tile(step_parameters, tile_path)
            yield (tile_parameters, tile)

    def save_tile(
        self,
        step_parameters: StepParameters,
        tile_parameters: TileParameters,
        tile: TileData,
    ) -> None:
        tile_path = self._get_tile_path(step_parameters, tile_parameters)
        if step_parameters.data_type == np.ndarray:
            np.save(tile_path, tile)
        elif step_parameters.data_type == gpd.GeoDataFrame:
            assert isinstance(tile, gpd.GeoDataFrame)
            tile.to_file(tile_path)
        else:
            raise Exception(
                f"Unsupported data type: {str(step_parameters.data_type)}"
            )
