import logging
import xml.etree.ElementTree as ET

import gpxpy.gpx

from .data_filters import (
    discard_resample_gps_data,
    linear_resample_gps_data,
    lpf_resample_gps_data,
)
from .metadata_manager import extract_gps_info
from .mp4_manager import MP4Manager

logger = logging.getLogger(__name__)  # pylint: disable=C0103


class OsmoGps:
    gps_data = None
    inputs = None
    input_frame_rate = None
    output_frequency = None
    resampling_method = None
    extract_extensions = False

    def __init__(self, inputs, timezone_offset=0, extract_extensions=False):
        if inputs is None:
            raise ValueError("inputs cannot be None")
        self.inputs = inputs
        self.timezone_offset = timezone_offset
        self.extract_extensions = extract_extensions

        self.extract()

    def extract(self):

        logger.info(f"Running extract command with inputs: {self.inputs}")

        self.gps_data = []
        for i, input_file in enumerate(self.inputs, start=1):
            logger.info(f"Processing file {i}/{len(self.inputs)}: {input_file}")

            mp4 = MP4Manager(input_file)
            metadata = mp4.get_metadata()

            gps_info, input_frame_rate = extract_gps_info(
                metadata, self.timezone_offset, self.extract_extensions
            )
            logger.info(f"Frame rate: {input_frame_rate}")
            self.input_frame_rate = input_frame_rate
            logger.info(f"Extracted {len(gps_info)} GPS data points.")

            self.gps_data.extend(gps_info)

    def resample(
        self,
        output_frequency=None,
        resampling_method=None,
    ):
        self.resampling_method = resampling_method
        if self.resampling_method is not None:
            if self.resampling_method not in ["discard", "linear", "lpf", "none"]:
                raise ValueError(
                    "resampling_method must be one of "
                    "'discard', 'linear', 'lpf', 'none'"
                )
            self.output_frequency = output_frequency
            if self.resampling_method in ["discard", "linear", "lpf"]:
                if self.output_frequency is None:
                    raise ValueError(
                        "output_frequency cannot be None when "
                        "resampling_method is not 'none'"
                    )
            logger.info(
                f"Resampling GPS data with method: {self.resampling_method}, "
                f"output frequency: {self.output_frequency}"
            )
            if self.resampling_method == "linear":
                resampled_data = linear_resample_gps_data(
                    self.gps_data, self.input_frame_rate, self.output_frequency
                )
            elif self.resampling_method == "lpf":
                resampled_data = lpf_resample_gps_data(
                    self.gps_data, self.input_frame_rate, self.output_frequency
                )
            elif self.resampling_method == "discard":
                resampled_data = discard_resample_gps_data(
                    self.gps_data, self.input_frame_rate, self.output_frequency
                )
            self.gps_data = resampled_data

    def save_gpx(self, output_file):
        if self.gps_data is not None and self.gps_data != []:
            gpx = gpxpy.gpx.GPX()
            gpx.creator = "pyosmogps -- https://github.com/francescocaponio/pyosmogps"
            track = gpxpy.gpx.GPXTrack()
            gpx.tracks.append(track)
            segment = gpxpy.gpx.GPXTrackSegment()
            track.segments.append(segment)

            for i in range(len(self.gps_data)):
                point = gpxpy.gpx.GPXTrackPoint(
                    latitude=self.gps_data[i]["latitude"],
                    longitude=self.gps_data[i]["longitude"],
                    elevation=self.gps_data[i]["altitude"],
                    time=self.gps_data[i]["timeinfo"],
                )

                if self.extract_extensions:
                    extensions = ET.Element("extensions")

                    acc_x_ext = ET.SubElement(extensions, "acc_x")
                    acc_x_ext.text = f"{self.gps_data[i]['camera_acc_x']:.3f}"

                    acc_y_ext = ET.SubElement(extensions, "acc_y")
                    acc_y_ext.text = f"{self.gps_data[i]['camera_acc_y']:.3f}"

                    acc_z_ext = ET.SubElement(extensions, "acc_z")
                    acc_z_ext.text = f"{self.gps_data[i]['camera_acc_z']:.3f}"

                    der_x_ext = ET.SubElement(extensions, "der_x")
                    der_x_ext.text = f"{self.gps_data[i]['remote_der_x']:.3f}"

                    der_y_ext = ET.SubElement(extensions, "der_y")
                    der_y_ext.text = f"{self.gps_data[i]['remote_der_y']:.3f}"

                    der_z_ext = ET.SubElement(extensions, "der_z")
                    der_z_ext.text = f"{self.gps_data[i]['remote_der_z']:.3f}"

                    point.extensions.append(extensions)
                segment.points.append(point)

            with open(output_file, "w") as gpx_file:
                gpx_file.write(gpx.to_xml())

            logger.info(f"GPS data written to {output_file}")
            return True
        else:
            logger.info("No GPS data extracted.")
            return False

    def get_altitude(self):
        return [point["altitude"] for point in self.gps_data]

    def get_latitude(self):
        return [point["latitude"] for point in self.gps_data]

    def get_longitude(self):
        return [point["longitude"] for point in self.gps_data]
