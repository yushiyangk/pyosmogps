import csv
import logging
import xml.etree.ElementTree as ET
from typing import Optional

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
    require_gps = True

    def __init__(self, inputs, timezone_offset=0, extract_extensions=False, require_gps=True):
        if inputs is None:
            raise ValueError("inputs cannot be None")
        self.inputs = inputs
        self.timezone_offset = timezone_offset
        self.extract_extensions = extract_extensions
        self.require_gps = require_gps

        self.extract()

    def extract(self):

        logger.info(f"Running extract command with inputs: {self.inputs}")

        self.gps_data = []
        for i, input_file in enumerate(self.inputs, start=1):
            logger.info(f"Processing file {i}/{len(self.inputs)}: {input_file}")

            mp4 = MP4Manager(input_file)
            metadata = mp4.get_metadata()

            gps_info, input_frame_rate = extract_gps_info(
                metadata, self.timezone_offset, self.extract_extensions, self.require_gps,
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

            if self.resampling_method != "none":
                if not self.require_gps:
                    logger.warning("When resampling is enabled, all data points without GPS information will be discarded.")
                    filtered_gps_data = []
                    for point in self.gps_data:
                        if _has_gps(point):
                            filtered_gps_data.append(point)
                    discard_count = len(self.gps_data) - len(filtered_gps_data)
                    if discard_count > 0:
                        logger.warning(f"Discarded {discard_count} out of {len(self.gps_data)} data points.")
                    self.gps_data = filtered_gps_data

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
            else:
                resampled_data = self.gps_data

            self.gps_data = resampled_data

    def save_gpx(self, output_file):
        if not self.require_gps:
            logger.warning("Data extracted without requiring GPS information. Data points without GPS information will not be included in the GPX file.")

        if self.gps_data is not None and self.gps_data != []:
            gpx = gpxpy.gpx.GPX()
            gpx.creator = "pyosmogps -- https://github.com/francescocaponio/pyosmogps"
            track = gpxpy.gpx.GPXTrack()
            gpx.tracks.append(track)
            segment = gpxpy.gpx.GPXTrackSegment()
            track.segments.append(segment)

            for i in range(len(self.gps_data)):
                gps_point = self.gps_data[i]

                if not _has_gps(gps_point):
                    logger.warning(f"Mising required GPS data in entry at index {i}. Skipping.")
                    continue

                point = gpxpy.gpx.GPXTrackPoint(
                    latitude=gps_point["latitude"],
                    longitude=gps_point["longitude"],
                    elevation=gps_point["altitude"],
                    time=gps_point["timeinfo"],
                )

                if self.extract_extensions:
                    extensions = ET.Element("extensions")

                    if "frame_id" in gps_point:
                        frame_id_ext = ET.SubElement(extensions, "fid")
                        frame_id_ext.text = str(gps_point["frame_id"])

                    if "rel_frame_time_microsecond" in gps_point:
                        rel_frame_time_ext = ET.SubElement(extensions, "t")
                        rel_frame_time_ext.text = str(gps_point["rel_frame_time_microsecond"])

                    if "iso" in gps_point:
                        iso_ext = ET.SubElement(extensions, "iso")
                        iso_ext.text = str(round(gps_point["iso"]))

                    if "shutter_speed" in gps_point:
                        shutter_speed_ext = ET.SubElement(extensions, "ss")
                        shutter_speed_values = gps_point["shutter_speed"]
                        shutter_speed_ext.text = str(shutter_speed_values[0]) + (
                            "/" + str(shutter_speed_values[1])
                            if len(shutter_speed_values) > 1 else ""
                        )

                    if "colour_temperature" in gps_point:
                        colour_temperature_ext = ET.SubElement(extensions, "wb")
                        colour_temperature_ext.text = str(gps_point["colour_temperature"])

                    if "camera_acc_x" in gps_point:
                        acc_x_ext = ET.SubElement(extensions, "acc_x")
                        acc_x_ext.text = f"{gps_point['camera_acc_x']:.3f}"

                    if "camera_acc_y" in gps_point:
                        acc_y_ext = ET.SubElement(extensions, "acc_y")
                        acc_y_ext.text = f"{gps_point['camera_acc_y']:.3f}"

                    if "camera_acc_z" in gps_point:
                        acc_z_ext = ET.SubElement(extensions, "acc_z")
                        acc_z_ext.text = f"{gps_point['camera_acc_z']:.3f}"

                    if "remote_der_x" in gps_point:
                        der_x_ext = ET.SubElement(extensions, "der_x")
                        der_x_ext.text = f"{gps_point['remote_der_x']:.3f}"

                    if "remote_der_y" in gps_point:
                        der_y_ext = ET.SubElement(extensions, "der_y")
                        der_y_ext.text = f"{gps_point['remote_der_y']:.3f}"

                    if "remote_der_z" in gps_point:
                        der_z_ext = ET.SubElement(extensions, "der_z")
                        der_z_ext.text = f"{gps_point['remote_der_z']:.3f}"

                    point.extensions.append(extensions)
                segment.points.append(point)

            with open(output_file, "w") as gpx_file:
                gpx_file.write(gpx.to_xml())

            logger.info(f"GPS data written to {output_file}")
            return True
        else:
            logger.info("No GPS data written.")
            return False

    def save_csv(self, output_file):
        if self.gps_data is not None and self.gps_data != []:
            fields = self._get_ordered_fields()
            if "frame_id" in fields:
                fields.remove("frame_id")
                fields.insert(0, "frame_id")

            with open(output_file, 'w', newline="") as csv_file:
                logger.info("Writing data to CSV file.")
                dict_writer = csv.DictWriter(
                    csv_file,
                    fieldnames=fields,
                    restval="",
                    extrasaction='raise',
                )

                dict_writer.writeheader()
                for point in self.gps_data:
                    dict_writer.writerow(point)
                logger.info(f"Data written to {output_file}")

                return True

        else:
            logger.info("No data written.")
            return False

    def _get_ordered_fields(self) -> list:
        if self.gps_data is None or len(self.gps_data) == 0:
            return []

        fields_linked_list: Optional[_LinkedListNode] = None
        fields_index = {}
        for point in self.gps_data:
            prev_field: Optional[str] = None
            for field in point.keys():
                if field not in fields_index:
                    if prev_field is None:
                        new_node = _LinkedListNode(field, next_node=fields_linked_list)
                        fields_linked_list = new_node
                    else:
                        prev_node = fields_index[prev_field]
                        new_node = _LinkedListNode(field, next_node=prev_node.next_node)
                        prev_node.next_node = new_node

                    fields_index[field] = new_node

                prev_field = field

        ordered_fields = []
        node = fields_linked_list
        while node is not None:
            ordered_fields.append(node.value)
            node = node.next_node

        return ordered_fields

    def get_altitude(self):
        return [point["altitude"] for point in self.gps_data]

    def get_latitude(self):
        return [point["latitude"] for point in self.gps_data]

    def get_longitude(self):
        return [point["longitude"] for point in self.gps_data]


class _LinkedListNode:
    def __init__(self, value: str, next_node: Optional['_LinkedListNode']=None):
        self.value = value
        self.next_node = next_node


def _has_gps(point: dict) -> bool:
    required_fields = {"timeinfo", "altitude", "longitude", "latitude"}
    return required_fields <= point.keys()
