from dataclasses import dataclass
import multiprocessing as mp
import numpy as np
import os
import re
from typing import Any, Callable, List, Tuple, Union
from tqdm import tqdm

from .clean_exit import CleanExit, kill_children, set_clean_exit


@dataclass
class TileParameters:
    start_x: int
    start_y: int
    width: int
    height: int


@dataclass
class PipelineParameters:
    endx: int
    endy: int
    startx: int = 0
    starty: int = 0
    tile_size: int = 100
    work_dir: str = ""
    log_dir: str = ""
    num_processes: int = 1


class PipelineHelper:
    def __init__(self, pipeline_parameters: PipelineParameters) -> None:
        self.pipeline_parameters = pipeline_parameters

    def get_path(
        self,
        step: str,
        file_extension: str,
        tile_parameters: Union[TileParameters, None],
    ) -> str:
        pp = self.pipeline_parameters
        if tile_parameters is None:
            tile_path = os.path.join(
                pp.work_dir,
                f"{step}.{file_extension}"
            )
        else:
            tile_path = os.path.join(
                pp.work_dir,
                f"{step}-tile"
                f"_{tile_parameters.start_x}-{tile_parameters.start_y}"
                f"_{tile_parameters.width}-{tile_parameters.height}"
                f".{file_extension}",
            )
        return tile_path

    def get_tile_glob(
        self,
        step: str,
        file_extension: str,
    ) -> str:
        pp = self.pipeline_parameters
        glob_pattern = os.path.join(
            pp.work_dir,
            f"{step}-tile_*_*"
            f".{file_extension}",
        )
        return glob_pattern

    def get_tile_params_from_file(
        self,
        step: str,
        filepath: str,
    ) -> Union[TileParameters, None]:
        pattern = f"{step}-tile_(?P<start_x>[0-9]*)-(?P<start_y>[0-9]*)" \
                  f"_(?P<width>[0-9]*)-(?P<height>[0-9]*)"
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

    # works for rasters (saved as npy)
    def get_region(
        self,
        step: str,
        file_extension: str,
        region_parameters: TileParameters,
    ) -> np.ndarray:
        pp = self.pipeline_parameters
        data = np.zeros(
            (region_parameters.width, region_parameters.height)
        )
        region_start_x = region_parameters.start_x
        region_start_y = region_parameters.start_y
        region_end_x = region_parameters.start_x + region_parameters.width
        region_end_y = region_parameters.start_y + region_parameters.height

        for start_x in range(pp.startx, pp.endx, pp.tile_size):
            if start_x + pp.tile_size < region_start_x:
                continue
            if start_x >= region_end_x:
                break

            for start_y in range(pp.starty, pp.endy, pp.tile_size):
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
                tile_path = self.get_path(
                    step,
                    file_extension,
                    tile_parameters,
                )
                tile = np.load(tile_path)
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

    def handle_exception(
        self,
        step: str,
        e: Exception,
        tile_parameters: Union[TileParameters, None],
    ) -> None:
        pp = self.pipeline_parameters
        pid = os.getpid()
        if tile_parameters is None:
            message = f"[{pid}] Exception in {step}: {e}\n"
        else:
            message = f"[{pid}] Exception in {step} at " \
                f"({tile_parameters.start_x}, {tile_parameters.start_y}): " \
                f"{e}\n"
        filepath = os.path.join(pp.log_dir, f"log-{pid}")
        with open(filepath, 'w') as file:
            file.write(message)


# First Any is StepHelper.
StepFunction = Callable[[TileParameters, Any], Any]


@dataclass
class StepParameters:
    name: str
    function: StepFunction
    file_extension: Union[str, None] = None


class StepHelper:
    def __init__(
        self,
        pipeline_helper: PipelineHelper,
        curr_step_parameters: StepParameters,
        prev_step_parameters: Union[StepParameters, None],
    ):
        self.pipeline_helper = pipeline_helper
        self.curr_step_parameters = curr_step_parameters
        self.prev_step_parameters = prev_step_parameters

    def handle_exception(
        self,
        e: Exception,
        tile_parameters: Union[TileParameters, None],
    ) -> None:
        return self.pipeline_helper.handle_exception(
            self.curr_step_parameters.name,
            e,
            tile_parameters
        )

    def get_curr_path(
        self,
        tile_parameters: Union[TileParameters, None],
    ) -> str:
        if self.curr_step_parameters.file_extension is None:
            raise Exception("Current step does not have a file extension.")

        return self.pipeline_helper.get_path(
            self.curr_step_parameters.name,
            self.curr_step_parameters.file_extension,
            tile_parameters,
        )

    def get_prev_path(
        self,
        tile_parameters: Union[TileParameters, None],
    ) -> str:
        if self.prev_step_parameters is None:
            raise Exception("No previous step")
        if self.prev_step_parameters.file_extension is None:
            raise Exception("Previous step does not have a file extension.")

        return self.pipeline_helper.get_path(
            self.prev_step_parameters.name,
            self.prev_step_parameters.file_extension,
            tile_parameters,
        )

    def get_prev_tile_glob(self) -> str:
        if self.prev_step_parameters is None:
            raise Exception("No previous step")
        if self.prev_step_parameters.file_extension is None:
            raise Exception("Previous step does not have a file extension.")

        return self.pipeline_helper.get_tile_glob(
            self.prev_step_parameters.name,
            self.prev_step_parameters.file_extension,
        )

    def get_prev_region(
        self,
        region_parameters: TileParameters,
    ) -> np.ndarray:
        if self.prev_step_parameters is None:
            raise Exception("No previous step")
        if self.prev_step_parameters.file_extension is None:
            raise Exception("Previous step does not have a file extension.")

        return self.pipeline_helper.get_region(
            self.prev_step_parameters.name,
            self.prev_step_parameters.file_extension,
            region_parameters,
        )


class Step:
    def __init__(
        self,
        pipeline_parameters: PipelineParameters,
        step_parameters: StepParameters,
        step_helper: StepHelper,
    ) -> None:
        self.pipeline_parameters = pipeline_parameters
        self.step_parameters = step_parameters
        self.step_helper = step_helper

    def _generate_tiles(self) -> List[TileParameters]:
        pp = self.pipeline_parameters
        all_tile_parameters = [
            TileParameters(x, y, pp.tile_size, pp.tile_size)
            for x in range(pp.startx, pp.endx, pp.tile_size)
            for y in range(pp.starty, pp.endy, pp.tile_size)
        ]
        return all_tile_parameters

    @staticmethod
    def _step_function_wrapper(args: Tuple[
        StepParameters,
        StepHelper,
        TileParameters,
    ]) -> None:
        try:
            step_parameters, step_helper, tile_parameters = args
            step_parameters.function(tile_parameters, step_helper)
        except CleanExit:
            print(f"[{os.getpid()}] clean exit")
            pass
        except Exception as e:
            step_helper.handle_exception(e, tile_parameters)

    def _process_tiles(
        self,
        all_tile_parameters: List[TileParameters],
    ) -> None:
        pp = self.pipeline_parameters
        all_args = [(
            self.step_parameters,
            self.step_helper,
            tile_parameters,
        ) for tile_parameters in all_tile_parameters]

        pool = mp.Pool(processes=pp.num_processes)
        try:
            for _ in tqdm(
                pool.imap_unordered(self._step_function_wrapper, all_args),
                total=len(all_args),
                desc=f"[{self.step_parameters.name}] Processing tiles"
            ):
                pass
            pool.close()
            pool.join()
        except Exception as e:
            kill_children()
            raise e

    def process(self) -> Any:
        all_tile_parameters = self._generate_tiles()
        self._process_tiles(all_tile_parameters)


class Pipeline:
    def __init__(
        self,
        all_step_parameters: List[StepParameters],
        union_function: Callable[..., Any],
        pipeline_parameters: PipelineParameters,
    ) -> None:
        set_clean_exit()

        self.all_step_parameters = all_step_parameters
        self.union_function = union_function
        self.pipeline_parameters = pipeline_parameters
        self.pipeline_helper = PipelineHelper(pipeline_parameters)

    def run(self) -> None:
        prev_step_parameters = None
        for i, curr_step_parameters in enumerate(self.all_step_parameters):
            step_helper = StepHelper(
                self.pipeline_helper,
                curr_step_parameters,
                prev_step_parameters,
            )

            step = Step(
                self.pipeline_parameters,
                curr_step_parameters,
                step_helper,
            )
            step.process()

            prev_step_parameters = curr_step_parameters

        step_helper = StepHelper(
            self.pipeline_helper,
            StepParameters(
                name="union",
                function=self.union_function,
            ),
            prev_step_parameters,
        )
        try:
            self.union_function(step_helper)
        except CleanExit:
            print(f"[{os.getpid()}] clean exit")
            pass
        except Exception as e:
            step_helper.handle_exception(e, None)
