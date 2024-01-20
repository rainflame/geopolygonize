from dataclasses import dataclass
from enum import Enum
import multiprocessing
import tempfile
from typing import Union


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
        parallelization: bool,
        store: Store,
        disk_config: Union[DiskConfig, None] = None,
    ):
        self.parallelization = parallelization
        num_processes = 1
        if parallelization:
            num_processes = multiprocessing.cpu_count()
        self.num_processes = num_processes

        self.store = store
        match store:
            case Store.Memory:
                if self.parallelization:
                    # Avoid sharing memory between processes.
                    # Doing this correctly while avoiding copying lots
                    # of data between processes seems rather tricky,
                    # so we avoid it for now.
                    # https://docs.python.org/3/library/multiprocessing.html#sharing-state-between-processes
                    raise Exception(
                        "Do not use memory to store intermediate data "
                        "if using parallelization. Use disk instead. "
                    )
            case Store.Disk:
                if disk_config is None:
                    raise Exception("Expected disk config for disk option.")
                self.disk_config = disk_config
            case _:
                raise Exception(f"Store {store} is not supported.")

        self.log_dir = tempfile.mkdtemp()


class StandardConfig(Config):
    def __init__(self):
        parallelization = False
        store = Store.Memory
        super().__init__(parallelization, store)


class LargeConfig(Config):
    def __init__(self):
        parallelization = True
        store = Store.Disk
        work_dir = tempfile.mkdtemp()
        disk_config = DiskConfig(work_dir=work_dir, keep=False)
        super().__init__(parallelization, store, disk_config=disk_config)
        print(f"Working directory: {self.disk_config.work_dir}")


class DebugConfig(Config):
    def __init__(
        self,
        work_dir: Union[str, None] = None,
    ):
        parallelization = True
        store = Store.Disk
        if work_dir is None:
            work_dir = tempfile.mkdtemp()
        disk_config = DiskConfig(work_dir=work_dir, keep=True)
        super().__init__(parallelization, store, disk_config=disk_config)
