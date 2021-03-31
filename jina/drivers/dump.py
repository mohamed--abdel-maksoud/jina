import os
import sys
from typing import Optional, Iterable, Tuple

import numpy as np

from jina.drivers import BaseExecutableDriver
from jina.enums import BetterEnum


class DumpDriver(BaseExecutableDriver):
    """A Driver that calls the dump method of the Executor

    :param executor: the executor to which we attach the driver
    :param args: passed to super().__init__
    :param kwargs: passed to super().__init__
    """

    def __init__(
        self,
        executor: Optional[str] = None,
        *args,
        **kwargs,
    ):
        super().__init__(executor, 'dump', *args, **kwargs)

    def __call__(self, *args, **kwargs):
        """Call the Dump method of the Indexer to which the Driver is attached

        :param args: passed to the exec_fn
        :param kwargs: passed to the exec_fn
        """
        self.exec_fn(self.req.path, self.req.shards, self.req.formats, *args, **kwargs)


class DumpPersistor:
    """
    Class for creating and importing from dumps

    Do NOT instantiate. Only provides static methods
    """

    @staticmethod
    def export_dump_streaming(
        path: str,
        shards: int,
        size: int,
        data: Iterable[Tuple[str, np.array, bytes]],
    ):
        """Export the data to a path, based on sharding,

        :param path: path to dump
        :param shards: the nr of shards this pea is part of
        :param size: total amount of entries
        :param data: the generator of the data (ids, vectors, metadata)
        """
        if os.path.exists(path):
            raise Exception(f'path for dump {path} already exists. Not dumping...')
        size_per_shard = size // shards
        extra = size % shards
        shard_range = list(range(shards))
        for shard_id in shard_range:
            if shard_id == shard_range[-1]:
                size_this_shard = size_per_shard + extra
            else:
                size_this_shard = size_per_shard
            shard_path = os.path.join(path, str(shard_id))
            shard_written = 0
            os.makedirs(shard_path)
            vectors_fh, metas_fh, ids_fh = DumpPersistor._get_file_handlers(shard_path)
            while shard_written < size_this_shard:
                id_, vec, meta = next(data)
                vec_bytes = vec.tobytes()
                vectors_fh.write(
                    len(vec_bytes).to_bytes(BYTE_PADDING, sys.byteorder) + vec_bytes
                )
                metas_fh.write(len(meta).to_bytes(BYTE_PADDING, sys.byteorder) + meta)
                ids_fh.write(id_ + '\n')
                shard_written += 1
            vectors_fh.close()
            metas_fh.close()
            ids_fh.close()

    @staticmethod
    def import_vectors(path: str, pea_id: str):
        """Import id and vectors

        :param path: the path to the dump
        :param pea_id: the id of the pea (as part of the shards)
        :return: the generators for the ids and for the vectors
        """
        path = os.path.join(path, pea_id)
        ids_gen = DumpPersistor._ids_gen(path)
        vecs_gen = DumpPersistor._vecs_gen(path)
        return ids_gen, vecs_gen

    @staticmethod
    def import_metas(path: str, pea_id: str):
        """Import id and metadata

        :param path: the path of the dump
        :param pea_id: the id of the pea (as part of the shards)
        :return: the generators for the ids and for the metadata
        """
        path = os.path.join(path, pea_id)
        ids_gen = DumpPersistor._ids_gen(path)
        metas_gen = DumpPersistor._metas_gen(path)
        return ids_gen, metas_gen

    @staticmethod
    def _ids_gen(path):
        with open(os.path.join(path, 'ids'), 'r') as ids_fh:
            for l in ids_fh:
                yield l.strip()

    @staticmethod
    def _vecs_gen(path):
        with open(os.path.join(path, 'vectors'), 'rb') as vectors_fh:
            while True:
                next_size = vectors_fh.read(BYTE_PADDING)
                next_size = int.from_bytes(next_size, byteorder=sys.byteorder)
                if next_size:
                    vec = np.frombuffer(
                        vectors_fh.read(next_size),
                        dtype=np.float64,
                    )
                    yield vec
                else:
                    break

    @staticmethod
    def _metas_gen(path):
        with open(os.path.join(path, 'metas'), 'rb') as metas_fh:
            while True:
                next_size = metas_fh.read(BYTE_PADDING)
                next_size = int.from_bytes(next_size, byteorder=sys.byteorder)
                if next_size:
                    meta = metas_fh.read(next_size)
                    yield meta
                else:
                    break

    @staticmethod
    def _get_file_handlers(shard_path):
        vectors_fh = open(os.path.join(shard_path, 'vectors'), 'wb')
        metas_fh = open(os.path.join(shard_path, 'metas'), 'wb')
        ids_fh = open(os.path.join(shard_path, 'ids'), 'w')
        return vectors_fh, metas_fh, ids_fh


BYTE_PADDING = 4


class DumpTypes(BetterEnum):
    """The enum of dump formats"""

    DEFAULT = 0
    NUMPY = 1
