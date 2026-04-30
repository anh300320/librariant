from abc import ABC, abstractmethod


class BaseBackgroundWorker[T](ABC):
    @abstractmethod
    def run(self, task_data: T) -> None:
        raise NotImplementedError
