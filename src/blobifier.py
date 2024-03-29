from typing import Any, List

import numpy as np
from scipy import ndimage
from scipy.stats import mode


# Assumes that the input data will not use negative values.
NULL_VALUE = -1


class Blobifier:
    def __init__(
        self,
        data: np.ndarray,
        min_blob_size: int = 5,
        invalid_values: List[Any] = [],
    ) -> None:
        self.data = data
        self.invalid_values = invalid_values
        self.min_blob_size = min_blob_size

    def _mask_invalid_values(self) -> np.ndarray:
        mask = np.zeros_like(self.data, dtype=bool)
        for invalid_value in self.invalid_values:
            per_value_mask = self.data == invalid_value
            mask = np.logical_or(mask, per_value_mask)
        return mask

    # Return a mask with True for pixels that are part of small blobs,
    # else False.
    def _identify_blobs(self) -> np.ndarray:
        # We have 2^31-1 = 2147483647 values available to use.
        # Make sure the image is reasonably small to not have so many blobs,
        # i.e. width * height < 2^31-1.
        blob_raster = np.zeros_like(self.data, dtype=np.int32)
        unique_values = np.unique(self.data)
        total_num_features = 0
        for uv in unique_values:
            binary_raster = np.zeros_like(self.data)
            binary_raster[self.data == uv] = 1
            binary_blob_raster, num_features = ndimage.label(binary_raster)
            mask = binary_raster > 0
            blob_raster[mask] = binary_blob_raster[mask] + total_num_features
            total_num_features += num_features
        return blob_raster

    def _mask_small_blobs(self, blob_raster: np.ndarray) -> np.ndarray:
        small_blob_mask = np.zeros_like(blob_raster, dtype=bool)
        all_pixel_values = blob_raster.ravel()
        component_sizes = np.bincount(all_pixel_values)
        small_components = np.where(component_sizes < self.min_blob_size)[0]
        for component_label in small_components:
            small_blob_mask[blob_raster == component_label] = True
        return small_blob_mask

    def _fill_blobs(self, mask: np.ndarray) -> np.ndarray:
        neighborhood = np.array([
            [1, 1, 1],
            [1, 1, 1],
            [1, 1, 1]
        ], dtype=np.uint8)

        def choose_value(x):
            center = x[4]
            selection = x[x != NULL_VALUE]
            if center == NULL_VALUE and not selection.size == 0:
                m = mode(selection, axis=None).mode
                return m
            else:
                return center

        blob_raster = self.data.copy()
        blob_raster[mask] = NULL_VALUE
        while np.any(blob_raster == NULL_VALUE):
            result = ndimage.generic_filter(
                blob_raster,
                choose_value,
                footprint=neighborhood,
                mode="constant",
                cval=NULL_VALUE,
            )
            blob_raster = result
        return blob_raster

    def blobify(self):
        invalid_values_mask = self._mask_invalid_values()

        blob_raster = self._identify_blobs()
        small_blob_mask = self._mask_small_blobs(blob_raster)

        mask = np.logical_or(invalid_values_mask, small_blob_mask)

        cleaned_raster = self._fill_blobs(mask)
        return cleaned_raster
