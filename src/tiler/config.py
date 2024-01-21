from dataclasses import dataclass
from enum import Enum
import math
import multiprocessing
import tempfile
from typing import Union

from .types import PipelineParameters


MIN_TILE_SIZE = 10
MAX_TILE_SIZE = 1000


class Store(Enum):
    Memory = "Memory"
    Disk = "Disk"


@dataclass
class DiskConfig:
    work_dir: str
    keep: bool


class Config:
    def __init__(
        self,
        pipeline_parameters: PipelineParameters,
        parallelization: bool,
        store: Store,
        independent: bool = False,
        disk_config: Union[DiskConfig, None] = None,
    ):
        self.independent = independent
        self.parallelization = parallelization
        num_processes = 1
        if parallelization:
            num_processes = multiprocessing.cpu_count()
        self.num_processes = num_processes

        self.tile_size = min(max(int(math.sqrt(float(
            pipeline_parameters.width * \
            pipeline_parameters.height
        ) / float(self.num_processes))), MIN_TILE_SIZE), MAX_TILE_SIZE)
        print(f"Using tile_size {self.tile_size}")

        self.store = store
        match store:
            case Store.Memory:
                if self.parallelization and not independent:
                    # Avoid sharing memory between processes.
                    # Doing this correctly while avoiding copying lots
                    # of data between processes seems rather tricky,
                    # so we avoid it for now.
                    # https://docs.python.org/3/library/multiprocessing.html#sharing-state-between-processes
                    raise Exception(
                        "Do not use memory to store intermediate data "
                        "if tiles are not independent and "
                        "if you are using parallelization. "
                        "Use disk instead. "
                    )
            case Store.Disk:
                if disk_config is None:
                    raise Exception("Expected disk config for disk option.")
                self.disk_config = disk_config
            case _:
                raise Exception(f"Store {store} is not supported.")

        self.log_dir = tempfile.mkdtemp()


class StandardConfig(Config):
    def __init__(self, pipeline_parameters: PipelineParameters) -> None:
        parallelization = False
        store = Store.Memory
        super().__init__(pipeline_parameters, parallelization, store)


class IndependentConfig(Config):
    def __init__(self, pipeline_parameters: PipelineParameters) -> None:
        parallelization = True
        store = Store.Memory
        super().__init__(
            pipeline_parameters,
            parallelization,
            store,
            independent=True,
        )


class LargeConfig(Config):
    def __init__(self, pipeline_parameters: PipelineParameters) -> None:
        parallelization = True
        store = Store.Disk
        work_dir = tempfile.mkdtemp()
        disk_config = DiskConfig(work_dir=work_dir, keep=False)
        super().__init__(
            pipeline_parameters,
            parallelization,
            store,
            disk_config=disk_config,
        )
        print(f"Working directory: {self.disk_config.work_dir}")


class DebugConfig(Config):
    def __init__(
        self,
        pipeline_parameters: PipelineParameters,
        work_dir: Union[str, None] = None,
    ) -> None:
        parallelization = True
        store = Store.Disk
        if work_dir is None:
            work_dir = tempfile.mkdtemp()
        disk_config = DiskConfig(work_dir=work_dir, keep=True)
        super().__init__(
            pipeline_parameters,
            parallelization,
            store,
            disk_config=disk_config,
        )


MAX_UNITS = 1.0e+8


def create_config(pipeline_parameters: PipelineParameters) -> Config:
    config: Config
    if pipeline_parameters.debug:
        config = DebugConfig(pipeline_parameters)
        print("Using debug configuration")
    else:
        # The data cannot be fully stored in memory
        # so we store it on disk instead.
        num_units = (pipeline_parameters.width * pipeline_parameters.height) \
            * len(pipeline_parameters.steps)
        if num_units > MAX_UNITS:
            config = LargeConfig(pipeline_parameters)
            print("Using large configuration")
        else:
            if pipeline_parameters.independent:
                config = IndependentConfig(pipeline_parameters)
                print("Using tile-independence configuration")
            else:
                config = StandardConfig(pipeline_parameters)
                print("Using standard configuration")

    if config.parallelization:
        print(f"Using {config.num_processes} processes.")
    if config.store == Store.Disk:
        print(f"Working directory: {config.disk_config.work_dir}")
    print(f"Logs directory: {config.log_dir}")
    return config
