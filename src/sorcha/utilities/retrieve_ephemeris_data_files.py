import argparse
import concurrent.futures
import os
import pooch

from functools import partial
from sorcha.ephemeris.simulation_data_files import (
    make_retriever,
    DATA_FILES_TO_DOWNLOAD,
    META_KERNEL,
    ORDERED_KERNEL_FILES,
)


def _decompress(fname, action, pup):
    """Override the functionality of Pooch's `Decompress` class so that the resulting
    decompressed file uses the original file name without the compression extension.
    For instance `filename.json.bz` will be decompressed and saved as `filename.json`.

    Parameters
    ----------
    fname : str
        Original filename
    action : str
        One of []"download", "update", "fetch"]
    pup : pooch.Pooch
        The Pooch object that defines the location of the file.
    """
    known_extentions = [".gz", ".bz2", ".xz"]
    if os.path.splitext(fname)[-1] in known_extentions:
        pooch.Decompress(method="auto", name=os.path.splitext(fname)[0]).__call__(fname, action, pup)


def _remove_files(retriever: pooch.Pooch) -> None:
    """Utility to remove all the files tracked by the pooch retriever.

    Parameters
    ----------
    retriever : pooch.Pooch
        Pooch object that maintains the registry of files to download.
    """
    for file_name in DATA_FILES_TO_DOWNLOAD:
        file_path = retriever.fetch(file_name)
        print(f"Deleting file: {file_path}")
        os.remove(file_path)


def _build_meta_kernel_file(retriever: pooch.Pooch) -> None:
    """Builds a specific text file that will be fed into `spiceypy` that defines
    the list of spice kernel to load, as well as the order to load them.

    Parameters
    ----------
    retriever : pooch.Pooch
        Pooch object that maintains the registry of files to download
    """
    # build meta_kernel file path
    meta_kernel_file_path = os.path.join(retriever.abspath, META_KERNEL)

    # build a meta_kernel.txt file
    with open(meta_kernel_file_path, "w") as meta_file:
        meta_file.write("\\begindata\n\n")
        meta_file.write("KERNELS_TO_LOAD=(\n")
        for file_name in ORDERED_KERNEL_FILES:
            meta_file.write(f"    '{retriever.fetch(file_name)}',\n")
        meta_file.write(")\n\n")
        meta_file.write("\\begintext\n")


def main():
    # parse the input arguments
    parser = argparse.ArgumentParser(
        description="Fetch the NAIF high precision EOP kernel file store its checksum."
    )
    parser.add_argument(
        "--cache",
        type=str,
        default=pooch.os_cache("sorcha"),
        help="Local directory where downloaded files will be stored.",
    )
    parser.add_argument(
        "-f",
        "--force",
        action="store_true",
        help="Delete and re-download data files.",
    )
    args = parser.parse_args()

    # create the Pooch retriever that tracks and retrieves the requested files
    retriever = make_retriever(args.cache)

    # remove files if the user has requested re-downloading the files
    if args.force:
        _remove_files(retriever)

    # create a partial function of `Pooch.fetch` including the `_decompress` method
    fetch_partial = partial(retriever.fetch, processor=_decompress, progressbar=True)

    # download the data files in parallel
    with concurrent.futures.ThreadPoolExecutor() as executor:
        executor.map(fetch_partial, DATA_FILES_TO_DOWNLOAD)

    # build the meta_kernel.txt file
    _build_meta_kernel_file(retriever)


if __name__ == "__main__":
    main()