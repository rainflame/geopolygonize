import multiprocessing as mp
import os
import signal


class CleanExit(Exception):
    pass


def _raise_clean_exit(signal: int, frame) -> None:
    raise CleanExit("clean exit")


def set_clean_exit():
    signal.signal(signal.SIGINT, _raise_clean_exit)
    signal.signal(signal.SIGTERM, _raise_clean_exit)


def kill_children():
    active = mp.active_children()
    for child in active:
        child.kill()


def kill_self():
    os.kill(os.getpid(), signal.SIGKILL)
