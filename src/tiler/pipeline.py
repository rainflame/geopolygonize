"""
Allows the user to specify a series of steps,
where each step is tiled to allow incremental progress
and potentially parallelization.
"""

import os
import shutil
import traceback
from typing import Iterator, List, Tuple

import multiprocessing as mp
from tqdm import tqdm

from src.utils.clean_exit import kill_children, set_clean_exit, CleanExit
from .config import Config
from .step_helper import StepHelper
from .store import create_tile_store, Store
from .types import (
    PipelineParameters,
    TileParameters,
    StepParameters,
    TileData,
    StepFunction,
)


def _step_function_wrapper(args: Tuple[
    Config,
    StepFunction,
    StepHelper,
    StepParameters,
    TileParameters,
]) -> None:
    try:
        (
            config,
            step_function,
            step_helper,
            step_parameters,
            tile_parameters
        ) = args

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
        pid = os.getpid()
        step_message = f" in {step_parameters.name}"
        tile_message =\
            f" at ({tile_parameters.start_x}, {tile_parameters.start_y})"
        stack_trace = "".join(traceback.format_tb(e.__traceback__))
        message = \
            f"[{pid}] Exception{step_message}{tile_message}:" \
            f"\n{stack_trace}\n{e}\n"

        filepath = os.path.join(
            config.log_dir, f"log-{pid}"
        )
        with open(filepath, 'w') as file:
            file.write(message)


class Pipeline:
    def __init__(
        self,
        pipeline_parameters: PipelineParameters,
        config: Config,
    ) -> None:
        self.pipeline_parameters = pipeline_parameters
        self.config = config

    def _generate_tiles(self) -> List[TileParameters]:
        pp = self.pipeline_parameters
        all_tile_parameters = [
            TileParameters(x, y, self.config.tile_size, self.config.tile_size)
            for x in range(0, pp.width, self.config.tile_size)
            for y in range(0, pp.height, self.config.tile_size)
        ]
        return all_tile_parameters

    def _handle_exception(self, e: Exception) -> None:
        pid = os.getpid()
        stack_trace = "".join(traceback.format_tb(e.__traceback__))
        message = \
            f"[{pid}] Exception:" \
            f"\n{stack_trace}\n{e}\n"

        filepath = os.path.join(
            self.config.log_dir, f"log-{pid}"
        )
        with open(filepath, 'w') as file:
            file.write(message)

    def run(self) -> None:
        pass

    def cleanup(self) -> None:
        if self.config.store == Store.Disk:
            if not self.config.disk_config.keep:
                work_dir = self.config.disk_config.work_dir
                print(
                    f"Removing working directory: {work_dir}"
                )
                shutil.rmtree(work_dir)


class TilePipeline(Pipeline):
    def __init__(
        self,
        pipeline_parameters: PipelineParameters,
        config: Config,
    ) -> None:
        if not config.parallelization:
            raise Exception(
                "Expect parallelization when processing tile-wise."
            )
        super().__init__(pipeline_parameters, config)

    @staticmethod
    def _process_tile(args: Tuple[
        Config,
        PipelineParameters,
        TileParameters,
    ]) -> Tuple[TileParameters, TileData]:
        config, pipeline_parameters, tile_parameters = args
        try:
            tile_store = create_tile_store(pipeline_parameters, config)
            prev_step_parameters = None
            for i, (curr_step_parameters, curr_step_function)\
                    in enumerate(pipeline_parameters.steps):
                step_helper = StepHelper(
                    config,
                    tile_store,
                    curr_step_parameters,
                    prev_step_parameters,
                )

                _step_function_wrapper((
                    config,
                    curr_step_function,
                    step_helper,
                    curr_step_parameters,
                    tile_parameters,
                ))
                prev_step_parameters = curr_step_parameters

            # return data for union
            step_helper = StepHelper(
                config,
                tile_store,
                None,
                prev_step_parameters,
            )
            tile = step_helper.get_prev_tile(tile_parameters)
            return tile_parameters, tile
        except CleanExit:
            print(f"[{os.getpid()}] clean exit")
            raise CleanExit()

    def _parallel_process_tiles(
        self,
        all_tile_parameters: List[TileParameters],
    ) -> Iterator[Tuple[TileParameters, TileData]]:
        pool = mp.Pool(processes=self.config.num_processes)
        all_args = [(
            self.config,
            self.pipeline_parameters,
            tile_parameters,
        ) for tile_parameters in all_tile_parameters]

        for (tile_parameters, tile) in tqdm(
            pool.imap_unordered(self._process_tile, all_args),
            total=len(all_args),
            desc="Processing tiles"
        ):
            yield tile_parameters, tile

        pool.close()
        pool.join()

    def run(self) -> None:
        try:
            def generate():
                all_tile_parameters = self._generate_tiles()
                return self._parallel_process_tiles(all_tile_parameters)

            self.pipeline_parameters.union_function(generate)
        except Exception as e:
            self._handle_exception(e)
            kill_children()


class StepPipeline(Pipeline):
    def __init__(
        self,
        pipeline_parameters: PipelineParameters,
        config: Config,
    ) -> None:
        super().__init__(pipeline_parameters, config)

    def _parallel_process_tiles(
        self,
        all_tile_parameters: List[TileParameters],
        step_parameters: StepParameters,
        step_function: StepFunction,
        step_helper: StepHelper,
    ) -> None:
        all_args = [(
            self.config,
            step_function,
            step_helper,
            step_parameters,
            tile_parameters,
        ) for tile_parameters in all_tile_parameters]
        pool = mp.Pool(processes=self.config.num_processes)

        for _ in tqdm(
            pool.imap_unordered(_step_function_wrapper, all_args),
            total=len(all_args),
            desc=f"[{step_parameters.name}] Processing tiles"
        ):
            pass

        pool.close()
        pool.join()

    def _single_process_tiles(
        self,
        all_tile_parameters: List[TileParameters],
        step_parameters: StepParameters,
        step_function: StepFunction,
        step_helper: StepHelper,
    ) -> None:
        for tile_parameters in tqdm(
            all_tile_parameters,
            total=len(all_tile_parameters),
            desc=f"[{step_parameters.name}] Processing tiles"
        ):
            _step_function_wrapper((
                self.config,
                step_function,
                step_helper,
                step_parameters,
                tile_parameters,
            ))

    def _process_step(
        self,
        step_parameters: StepParameters,
        step_function: StepFunction,
        step_helper: StepHelper,
    ) -> None:
        all_tile_parameters = self._generate_tiles()
        if self.config.parallelization:
            self._parallel_process_tiles(
                all_tile_parameters,
                step_parameters,
                step_function,
                step_helper,
            )
        else:
            self._single_process_tiles(
                all_tile_parameters,
                step_parameters,
                step_function,
                step_helper,
            )

    def run(self) -> None:
        try:
            tile_store = create_tile_store(
                self.pipeline_parameters,
                self.config,
            )

            prev_step_parameters = None
            for i, (curr_step_parameters, curr_step_function)\
                    in enumerate(self.pipeline_parameters.steps):
                step_helper = StepHelper(
                    self.config,
                    tile_store,
                    curr_step_parameters,
                    prev_step_parameters,
                )

                self._process_step(
                    curr_step_parameters,
                    curr_step_function,
                    step_helper,
                )

                prev_step_parameters = curr_step_parameters

            step_helper = StepHelper(
                self.config,
                tile_store,
                None,
                prev_step_parameters,
            )
            self.pipeline_parameters.union_function(step_helper.get_prev_tiles)
        except Exception as e:
            self._handle_exception(e)
            kill_children()


def pipe(pipeline_parameters: PipelineParameters, config: Config) -> None:
    set_clean_exit()
    try:
        pipeline: Pipeline
        if config.independent:
            pipeline = TilePipeline(pipeline_parameters, config)
        else:
            pipeline = StepPipeline(pipeline_parameters, config)
        pipeline.run()
        pipeline.cleanup()
    except CleanExit:
        print(f"[{os.getpid()}] clean exit")
        return
