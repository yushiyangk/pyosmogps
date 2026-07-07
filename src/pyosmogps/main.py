import argparse
import logging
import logging.config
import sys

from . import OsmoGps
from . import __version__ as pyosmogps_version

logger = logging.getLogger(__name__)  # pylint: disable=C0103


def _make_parser() -> argparse.ArgumentParser:
    # Separated so sphinx-argparse-cli can do its auto documentation magic.
    parser = argparse.ArgumentParser(
        description="Extract the GPS data from the Osmo Action video files",
        prog="pyosmogps",
    )
    parser.add_argument(
        "command",
        choices=["extract", "extract-csv", "merge"],
        help="Specify the command to run: 'extract' to extract "
        "GPS data to GPX format, 'extract-csv' "
        "to extract metadata (with or without GPS) to CSV format, "
        "or 'merge' to merge GPX files",
    )
    parser.add_argument(
        "inputs",
        nargs="+",
        help="Input file(s). Accepts a single file or multiple files.",
    )
    parser.add_argument(
        "output",
        help="Single output file.",
    )
    parser.add_argument(
        "--additional",
        "-a",
        action='store_true',
        help="Extract additional metadata (e.g. camera settings and accelerometer data) if available."
    )
    parser.add_argument(
        "--frequency",
        "-f",
        type=float,
        default=2.0,
        help="Set the output data frequency in Hz (default: 2 Hz).",
    )
    parser.add_argument(
        "--resampling-method",
        "-r",
        choices=["discard", "linear", "lpf", "none"],
        help="Set the method for resampling data: 'discard' to drop "
        "excess samples, 'linear' for linear interpolation, 'lpf' "
        "for low pass filtering, 'none' for no data reduction (default in "
        "'extract' mode: linear, default in other modes: none).",
    )
    parser.add_argument(
        "--timezone-offset",
        "-t",
        type=int,
        default=0,
        help="Set the timezone offset in hours (default: 0).",
    )
    parser.add_argument(
        "--version", "-v", action="version", version=f"%(prog)s {pyosmogps_version}"
    )
    return parser


def extract(save_method, inputs, output, frequency, resampling_method, timezone_offset=0, extract_extensions=False, require_gps=True) -> bool:
    try:
        gps = OsmoGps(
            inputs,
            timezone_offset=timezone_offset,
            extract_extensions=extract_extensions,
            require_gps=require_gps,
        )
        gps.resample(frequency, resampling_method)
        save_method(gps, output)

    except Exception as e:
        logger.error(f"Error: {e}")
        return False
    return True


def main() -> int:
    parser = _make_parser()
    if len(sys.argv) < 2:
        parser.print_help()
        parser.exit()

    args = parser.parse_args()

    if args.command == "extract":
        if not args.inputs or not args.output:
            parser.error(
                "'extract' command requires at least one input file and "
                "exactly one output file."
            )
        if args.resampling_method is None:
            if args.command == "extract":
                resampling_method = "linear"
            else:
                resampling_method = "none"
        else:
            resampling_method = args.resampling_method
        success = extract(
            OsmoGps.save_gpx,
            args.inputs,
            args.output,
            args.frequency,
            resampling_method,
            args.timezone_offset,
            extract_extensions=args.additional,
            require_gps=True,
        )
        return 0 if success else 1

    elif args.command == "extract-csv":
        if not args.inputs or not args.output:
            parser.error(
                "'extract' command requires at least one input file and "
                "exactly one output file."
            )
        success = extract(
            OsmoGps.save_csv,
            args.inputs,
            args.output,
            args.frequency,
            args.resampling_method,
            args.timezone_offset,
            extract_extensions=args.additional,
            require_gps=False,
        )
        return 0 if success else 1


    elif args.command == "merge":
        print("Running merge command...")
        # TODO: Implement merge command
    else:
        parser.print_help()
        parser.exit()

    return 0


if __name__ == "__main__":
    exit(main())
