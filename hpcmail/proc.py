import pickle
import psutil
import sys

from typing import List
from collections import namedtuple

proc_t = namedtuple('proc_t', ['pid', 'username', 'cmdline'])

def get_host_procs() -> List[proc_t]:
    return [proc_t(p.info['pid'], p.info['username'], p.info['cmdline']) \
                for p in psutil.process_iter(['pid', 'username', 'cmdline'])]

def serialize_host_procs(procs: List[proc_t]) -> bytes:
    return pickle.dumps(procs)

def deserialize_host_procs(procs: bytes) -> List[proc_t]:
    return pickle.loads(procs)
       
def main():
    procs = get_host_procs()
    serial_procs = serialize_host_procs(procs)
    sys.stdout.buffer.write(serial_procs)

if __name__ == '__main__':
    main()
