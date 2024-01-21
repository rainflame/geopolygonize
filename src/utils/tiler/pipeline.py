"""
Allows the user to specify a series of steps,
where each step is tiled to allow incremental progress
and potentially parallelization.
"""

import os
import shutil
from typing import List, Tuple

from src.utils.clean_exit import CleanExit, set_clean_exit
from .config import Config, DebugConfig, LargeConfig, StandardConfig, Store
from .step import Step, StepHelper
from .store import TileStore, TileMemory, TileDisk
from .types import (
    StepParameters,
    StepFunction,
    UnionFunction,
    PipelineParameters,
)


MAX_UNITS = 1.0e+8


class Pipeline:
    def __init__(
        self,
        all_step_parameters: List[Tuple[StepParameters, StepFunction]],
        union_function: UnionFunction,
        pipeline_parameters: PipelineParameters,
    ) -> None:
        set_clean_exit()

        self.all_step_parameters = all_step_parameters
        self.union_function = union_function
        self.pipeline_parameters = pipeline_parameters

        config: Config
        if self.pipeline_parameters.debug:
            config = DebugConfig()
            print("Using debug configuration")
        else:
            # The data cannot be fully stored in memory
            # so we store it on disk instead.
            num_units = (
                self.pipeline_parameters.endx - self.pipeline_parameters.startx
            ) * (
                self.pipeline_parameters.endy - self.pipeline_parameters.starty
            ) * (
                len(self.all_step_parameters)
            )
            if num_units > MAX_UNITS:
                config = LargeConfig()
                print("Using large configuration")
            else:
                config = StandardConfig()
                print("Using standard configuration")
        self.config = config

        if self.config.parallelization:
            print(f"Using {self.config.num_processes} processes.")
        if self.config.store == Store.Disk:
            print(f"Working directory: {config.disk_config.work_dir}")
        print(f"Logs directory: {self.config.log_dir}")

        self.tile_store: TileStore
        match config.store:
            case Store.Memory:
                self.tile_store = TileMemory(
                    config,
                    pipeline_parameters,
                )
            case Store.Disk:
                self.tile_store = TileDisk(
                    config,
                    pipeline_parameters,
                )
            case _:
                raise Exception(f"Store {config.store} is not supported.")

    def run(self) -> None:
        try:
            prev_step_parameters = None
            for i, (curr_step_parameters, curr_step_function)\
                    in enumerate(self.all_step_parameters):
                step_helper = StepHelper(
                    self.config,
                    self.tile_store,
                    curr_step_parameters,
                    prev_step_parameters,
                )

                step = Step(
                    self.config,
                    self.pipeline_parameters,
                    curr_step_parameters,
                    curr_step_function,
                    step_helper,
                )
                step.process()

                prev_step_parameters = curr_step_parameters

            step_helper = StepHelper(
                self.config,
                self.tile_store,
                None,
                prev_step_parameters,
            )
            try:
                self.union_function(step_helper.get_prev_tiles)
            except Exception as e:
                step_helper.handle_exception(e, None)

            if self.config.store == Store.Disk:
                if not self.config.disk_config.keep:
                    work_dir = self.config.disk_config.work_dir
                    print(
                        f"Removing working directory: {work_dir}"
                    )
                    shutil.rmtree(work_dir)
        except CleanExit:
            print(f"[{os.getpid()}] clean exit")
            return
