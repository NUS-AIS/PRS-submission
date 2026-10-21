"""In-memory case store for the UI: preprocessed stacks and per-case prediction state."""
from collections import OrderedDict
import threading
import uuid

from ct_preprocess import K

MAX_CASES = 8


class ApiError(Exception):
    """Error with a stable machine-readable code. The server renders it as
    {detail, code[, field_errors]}; `detail` stays a displayable string for the UI."""

    def __init__(self, status, code, detail, field_errors=None):
        super().__init__(detail)
        self.status, self.code, self.detail, self.field_errors = status, code, detail, field_errors

    def body(self):
        body = dict(detail=self.detail, code=self.code)
        if self.field_errors:
            body['field_errors'] = self.field_errors
        return body


class CaseStore:
    """Bounded LRU-by-insertion store; the oldest case is evicted when full."""

    def __init__(self, limit=MAX_CASES):
        self.limit = limit
        self._cases = OrderedDict()
        self._lock = threading.Lock()

    def remember(self, stack, name, **metadata):
        token = uuid.uuid4().hex
        with self._lock:
            while len(self._cases) >= self.limit:
                self._cases.popitem(last=False)
            self._cases[token] = dict(stack=stack, name=name, **metadata)
        return dict(token=token, name=name, slices=K, **metadata)

    def get(self, token):
        with self._lock:
            if token not in self._cases:
                raise ApiError(404, 'case_expired', 'Case expired. Upload or load it again.')
            return self._cases[token]

    def __len__(self):
        with self._lock:
            return len(self._cases)


CASES = CaseStore()
remember = CASES.remember
get_case = CASES.get
