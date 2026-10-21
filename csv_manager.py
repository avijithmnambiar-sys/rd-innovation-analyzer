import os                      # file-system helpers: exists, size, replace, remove
import tempfile                # creates the temporary file used for safe saving
import pandas as pd            # DataFrame handling and CSV reading/writing


class CSVManager:
    """Base class: safe loading and saving of one CSV file."""

    def __init__(self, file_path, columns):
        self.__file_path = os.path.abspath(str(file_path))  # double underscore = private (encapsulation)
        self._columns = list(columns)                        # single underscore = protected, subclasses may read it

    @property
    def file_path(self):                  # property = read-only access (no setter is defined)
        return self.__file_path          # outside code can read the path but cannot reassign it

    @property
    def columns(self):
        return list(self._columns)       # return a copy so callers cannot change our column list

    def _empty_frame(self):
        return pd.DataFrame(columns=self._columns)   # an empty table that still has the correct headers

    def load(self):
        if not os.path.exists(self.__file_path) or os.path.getsize(self.__file_path) == 0:
            return self._empty_frame()               # missing or zero-byte file -> empty table, no crash
        try:
            df = pd.read_csv(self.__file_path)       # read the CSV into a DataFrame
        except pd.errors.EmptyDataError:
            return self._empty_frame()               # file has no usable content
        except pd.errors.ParserError as err:
            raise ValueError(f"Not a valid CSV file: {err}")   # corrupted file -> clear error message
        missing = [c for c in self._columns if c not in df.columns]  # which expected columns are absent?
        if missing:
            raise ValueError(f"Missing columns: {', '.join(missing)}")  # wrong file structure
        return df[self._columns]                     # keep only expected columns, in the expected order

    def save(self, df):
        folder = os.path.dirname(self.__file_path)   # folder that holds the CSV
        os.makedirs(folder, exist_ok=True)           # create the data folder if it does not exist yet
        fd, temp_path = tempfile.mkstemp(dir=folder, suffix=".tmp")  # temp file in the SAME folder
        try:
            with os.fdopen(fd, "w", newline="", encoding="utf-8") as handle:
                df.to_csv(handle, index=False)       # write the full table into the temp file
            os.replace(temp_path, self.__file_path)  # atomic swap: original is replaced only if the write succeeded
        except Exception:
            if os.path.exists(temp_path):
                os.remove(temp_path)                 # clean up the half-written temp file
            raise                                    # pass the error up so the page can show it

    def summary(self, df=None):
        raise NotImplementedError("Each subclass must implement summary().")  # forces subclasses to define it