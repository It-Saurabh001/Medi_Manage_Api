"""Row type shared by non-sqlite3 database backends (see app/turso_http.py)."""


class Row(tuple):
    """Tuple whose values can also be read by column name, case-insensitively (like sqlite3.Row)."""

    def __new__(cls, values, keys, index):
        row = super().__new__(cls, values)
        row._keys, row._index = keys, index
        return row

    def __getitem__(self, key):
        if isinstance(key, str):
            try:
                key = self._index[key.lower()]
            except KeyError:
                raise IndexError("No item with that key") from None
        return tuple.__getitem__(self, key)

    def keys(self):
        return list(self._keys)
