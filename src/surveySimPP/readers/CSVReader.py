import pandas as pd
import logging
import sys

from surveySimPP.readers.ObjectDataReader import ObjectDataReader


class CSVDataReader(ObjectDataReader):
    """A class to read in object data files stored as CSV or whitespace
    separated values.

    Requires that the file's first column is ObjID.
    """

    def __init__(self, filename, sep="csv", header=-1, *args, **kwargs):
        """A class for reading the object data from a CSV file.

        Parameters:
        -----------
        filename (string): location/name of the data file.

        sep (string, optional): format of input file ("whitespace"/"comma"/"csv").

        header (int): The row number of the header. If not provided, does an automatic search.
        """
        super().__init__(*args, **kwargs)
        self.filename = filename

        if sep not in ["whitespace", "comma", "csv"]:
            pplogger = logging.getLogger(__name__)
            pplogger.error(f"ERROR: Unrecognized delimiter ({sep})")
            sys.exit(f"ERROR: Unrecognized delimiter ({sep})")
        self.sep = sep

        if header < 0:
            self.header_row = self._find_header_line()
        else:
            self.header_row = header

        # A table holding just the object ID for each row. Only populated
        # if we try to read data for specific object IDs.
        self.obj_id_table = None

    def _find_header_line(self):
        """Find the line number of the CSV header. Used for cases
        where the header is not the first line and we want to skip down.

        Returns:
        --------
        i (int) : The line index of the header.

        """
        with open(self.filename) as fh:
            for i, line in enumerate(fh):
                if line.startswith("ObjID"):
                    return i
                if i > 100:  # pragma: no cover
                    break

        pplogger = logging.getLogger(__name__)
        pplogger.error(
            "ERROR: OIFCSVReader: column headings not found. Ensure column headings exist in OIF output and first column is ObjID."
        )
        sys.exit(
            "ERROR: OIFCSVReader: column headings not found. Ensure column headings exist in OIF output and first column is ObjID."
        )
        return 0

    def read_rows(self, block_start=0, block_size=None, **kwargs):
        """Reads in a set number of rows from the input.

        Parameters:
        -----------
        block_start (int, optional): The 0-indexed row number from which
            to start reading the data. For example in a CSV file
            block_start=2 would skip the first two lines after the header
            and return data starting on row=2. [Default=0]

        block_size (int, optional): the number of rows to read in.
            Use block_size=None to read in all available data.
            [Default = None]

        Returns:
        -----------
        res_df (Pandas dataframe): dataframe of the auxilary data.
        """
        pplogger = logging.getLogger(__name__)

        # Skip the rows before the header and then begin_loc rows after the header.
        skip_rows = []
        if self.header_row > 0:
            skip_rows = [i for i in range(0, self.header_row)]
        if block_start > 0:
            skip_rows.extend([i for i in range(self.header_row + 1, self.header_row + 1 + block_start)])

        # Read the rows.
        if self.sep == "whitespace":
            res_df = pd.read_csv(
                self.filename,
                delim_whitespace=True,
                skiprows=skip_rows,
                nrows=block_size,
            )
        else:
            res_df = pd.read_csv(
                self.filename,
                delimiter=",",
                skiprows=skip_rows,
                nrows=block_size,
            )

        res_df = self.process_and_validate_input_table(res_df, **kwargs)
        return res_df

    def _build_id_map(self):
        """Builds a table of just the object IDs"""
        if self.obj_id_table is not None:
            return

        if self.sep == "whitespace":
            self.obj_id_table = pd.read_csv(
                self.filename,
                delim_whitespace=True,
                usecols=["ObjID"],
                header=self.header_row,
            )
        else:
            self.obj_id_table = pd.read_csv(
                self.filename,
                delimiter=",",
                usecols=["ObjID"],
                header=self.header_row,
            )

        self.obj_id_table = self._validate_object_id_column(self.obj_id_table)

    def read_objects(self, obj_ids, **kwargs):
        """Read in a chunk of data for given object IDs.

        Parameters:
        -----------
        obj_ids (list): A list of object IDs to use.

        Returns:
        -----------
        res_df (Pandas dataframe): The dataframe for the ephemerides.
        """
        self._build_id_map()

        # Create list of only the matching rows for these object IDs and the header row.
        skipped_row = [True] * self.header_row  # skip the pre-header
        skipped_row.extend([False])  # Keep the the column header
        skipped_row.extend(~self.obj_id_table["ObjID"].isin(obj_ids).values)

        # Read the rows.
        if self.sep == "whitespace":
            res_df = pd.read_csv(
                self.filename,
                delim_whitespace=True,
                skiprows=(lambda x: skipped_row[x]),
            )
        else:
            res_df = pd.read_csv(
                self.filename,
                delimiter=",",
                skiprows=(lambda x: skipped_row[x]),
            )
        res_df = self.process_and_validate_input_table(res_df, **kwargs)

        return res_df

    def process_and_validate_input_table(self, input_table, **kwargs):
        """Perform any input-specific processing and validation on the input table.
        Modifies the input dataframe in place.

        Note
        ----
        The base implementation includes filtering that is common to most
        input types. Subclasses should call super.process_and_validate()
        to ensure that the ancestor’s validation is also applied.

        Parameters:
        -----------
        input_table (Pandas dataframe): A loaded table.

        disallow_nan (bool, optional): if True then checks the data for
            NaNs or nulls.

        Returns:
        -----------
        input_table (Pandas dataframe): Returns the input dataframe modified in-place.
        """
        # Perform the parent class's validation (checking object ID column).
        input_table = super().process_and_validate_input_table(input_table, **kwargs)

        # Strip out the whitespace from the column names.
        input_table = input_table.rename(columns=lambda x: x.strip())

        # Check for NaNs or nulls.
        if "disallow_nan" in kwargs and kwargs["disallow_nan"]:  # pragma: no cover
            if input_table.isnull().values.any():
                pdt = input_table[input_table.isna().any(axis=1)]
                inds = str(pdt["ObjID"].values)
                outstr = f"ERROR: While reading table {self.filename} found uninitialised values ObjID: {str(inds)}."

                pplogger = logging.getLogger(__name__)
                pplogger.error(outstr)
                sys.exit(outstr)

        return input_table
