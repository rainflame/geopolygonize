import os
import traceback
from typing import Iterator, List, Tuple, Union

import multiprocessing as mp
from tqdm import tqdm

from src.utils.clean_exit import CleanExit, kill_children
from .config import Config
from .store import TileStore
from .types import (
    TileParameters,
    TileData,
    StepParameters,
    StepFunction,
    PipelineParameters,
)


# Used by the processes that execute a step.
class StepHelper:
    def __init__(
        self,
        config: Config,
        tile_store: TileStore,
        curr_step_parameters: Union[StepParameters, None],
        prev_step_parameters: Union[StepParameters, None],
    ):
        self.config = config
        self.tile_store = tile_store
        self.curr_step_parameters = curr_step_parameters
        self.prev_step_parameters = prev_step_parameters

    def handle_exception(
        self,
        e: Exception,
        tile_parameters: Union[TileParameters, None],
    ) -> None:
        pid = os.getpid()
        step_message = "" if self.curr_step_parameters is None else \
            f" in {self.curr_step_parameters.name}"
        tile_message = "" if tile_parameters is None else \
            f" at ({tile_parameters.start_x}, {tile_parameters.start_y})"
        stack_trace = "".join(traceback.format_tb(e.__traceback__))
        message = \
            f"[{pid}] Exception{step_message}{tile_message}:" \
            f"\n{stack_trace}\n{e}\n"

        filepath = os.path.join(
            self.config.log_dir, f"log-{pid}"
        )
        with open(filepath, 'w') as file:
            file.write(message)

    def has_curr_tile(
        self,
        tile_parameters: TileParameters,
    ) -> bool:
        if self.curr_step_parameters is None:
            raise Exception("No current step")

        return self.tile_store.has_tile(
            self.curr_step_parameters,
            tile_parameters,
        )

    def save_curr_tile(
        self,
        tile_parameters: TileParameters,
        tile: TileData,
    ) -> None:
        if self.curr_step_parameters is None:
            raise Exception("No current step")

        self.tile_store.save_tile(
            self.curr_step_parameters,
            tile_parameters,
            tile,
        )

    def get_prev_tile(
        self,
        tile_parameters: TileParameters,
    ) -> TileData:
        if self.prev_step_parameters is None:
            raise Exception("No previous step")

        return self.tile_store.get_tile(
            self.prev_step_parameters,
            tile_parameters,
        )

    def get_prev_region(
        self,
        region_parameters: TileParameters,
    ) -> TileData:
        if self.prev_step_parameters is None:
            raise Exception("No previous step")

        return self.tile_store.get_region(
            self.prev_step_parameters,
            region_parameters,
        )

    def get_prev_tiles(self) -> Iterator[Tuple[TileParameters, TileData]]:
        if self.prev_step_parameters is None:
            raise Exception("No previous step")

        return self.tile_store.get_all_tiles(
            self.prev_step_parameters,
        )


class Step:
    def __init__(
        self,
        config: Config,
        pipeline_parameters: PipelineParameters,
        step_parameters: StepParameters,
        step_function: StepFunction,
        step_helper: StepHelper,
    ) -> None:
        self.config = config
        self.pipeline_parameters = pipeline_parameters
        self.step_parameters = step_parameters
        self.step_function = step_function
        self.step_helper = step_helper

    def _generate_tiles(self) -> List[TileParameters]:
        pp = self.pipeline_parameters
        all_tile_parameters = [
            TileParameters(x, y, pp.tile_size, pp.tile_size)
            for x in range(0, pp.width, pp.tile_size)
            for y in range(0, pp.height, pp.tile_size)
        ]
        return all_tile_parameters

    @staticmethod
    def _step_function_wrapper(args: Tuple[
        StepFunction,
        StepHelper,
        TileParameters,
    ]) -> None:
        try:
            step_function, step_helper, tile_parameters = args

            if step_helper.has_curr_tile(tile_parameters):
                return

            step_function(
                tile_parameters,
                step_helper.get_prev_tile,
                step_helper.get_prev_region,
                step_helper.save_curr_tile,
            )
        except CleanExit:
            print(f"[{os.getpid()}] clean exit")
            raise CleanExit()
        except Exception as e:
            step_helper.handle_exception(e, tile_parameters)

    def _parallel_process_tiles(
        self,
        all_tile_parameters: List[TileParameters],
    ) -> None:
        all_args = [(
            self.step_function,
            self.step_helper,
            tile_parameters,
        ) for tile_parameters in all_tile_parameters]
        pool = mp.Pool(processes=self.config.num_processes)
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

    def _single_process_tiles(
        self,
        all_tile_parameters: List[TileParameters],
    ) -> None:
        for tile_parameters in tqdm(
            all_tile_parameters,
            total=len(all_tile_parameters),
            desc=f"[{self.step_parameters.name}] Processing tiles"
        ):
            self._step_function_wrapper((
                self.step_function,
                self.step_helper,
                tile_parameters,
            ))

    def process(self):
        all_tile_parameters = self._generate_tiles()
        if self.config.parallelization:
            self._parallel_process_tiles(all_tile_parameters)
        else:
            self._single_process_tiles(all_tile_parameters)
