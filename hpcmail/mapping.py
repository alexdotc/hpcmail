import csv
import os

from abc import ABC, abstractmethod
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Optional

@dataclass
class User:
    uid: int
    username: str
    firstname: Optional[str]
    lastname: Optional[str]

    def fullname(self) -> Optional[str]:
        if self.firstname and self.lastname:
            return self.firstname + ' ' + self.lastname
        return None

class EmailMapping(ABC):
    def __init__(self, *args):
        self.mapping = self.create(*args)
    
    @abstractmethod
    def create(self) -> dict:
        raise NotImplementedError

    @abstractmethod
    def search(self, s: str):
        raise NotImplementedError

class CSVEmailMapping(EmailMapping):
    def create(self, filename: os.PathLike, keyfield: str, fieldnames: Optional[Sequence]=None):
        mapping = {}
        with open(filename, 'r') as f:
            r = csv.DictReader(f, fieldnames)
            for row in r:
                mapping[row[keyfield]] = row
        return mapping

    def search(self, key):
        print(self.mapping) # TODO
