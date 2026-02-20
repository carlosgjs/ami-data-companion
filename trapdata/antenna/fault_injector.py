"""Fault injection utilities for testing worker robustness and error handling.

This module provides configurable error simulation for testing how the Antenna
service handles various failure scenarios including worker crashes, network errors,
image corruption, and permanent failures.

Environment Variables:
    AMI_TEST_WORKER_CRASH_RATE: Probability (0.0-1.0) of worker crashing during job processing
    AMI_TEST_NETWORK_ERROR_RATE: Probability of network errors during API calls
    AMI_TEST_CORRUPT_IMAGE_RATE: Probability of image appearing corrupted during download
    AMI_TEST_IMAGE_404_RATE: Probability of image returning 404 Not Found
    AMI_TEST_TRANSIENT_ERROR_RATE: Probability of transient failures (retryable)
    AMI_TEST_PERMANENT_ERROR_IMAGES: Comma-separated list of image URLs/IDs that always fail
    AMI_TEST_FAULT_INJECTION_ENABLED: Set to "true" to enable fault injection (default: false)

Example Usage:
    injector = FaultInjector()

    # Check if worker should crash
    injector.maybe_crash_worker("Processing job 123")

    # Simulate network error during API call
    if injector.maybe_network_error():
        raise requests.ConnectionError("Simulated network failure")

    # Check if image should return 404
    if injector.maybe_image_404("https://example.com/image.jpg"):
        raise requests.HTTPError("404 Not Found")
"""

import os
import random
import sys
from typing import Optional, Set

import requests

from trapdata.common.logs import logger


class FaultInjector:
    """Configurable fault injection for testing worker error handling."""

    def __init__(self):
        """Initialize fault injector with environment variable configuration."""
        self.enabled = (
            os.getenv("AMI_TEST_FAULT_INJECTION_ENABLED", "false").lower() == "true"
        )

        # Parse error rates from environment
        self.worker_crash_rate = self._parse_rate("AMI_TEST_WORKER_CRASH_RATE", 0.0)
        self.network_error_rate = self._parse_rate("AMI_TEST_NETWORK_ERROR_RATE", 0.0)
        self.corrupt_image_rate = self._parse_rate("AMI_TEST_CORRUPT_IMAGE_RATE", 0.0)
        self.image_404_rate = self._parse_rate("AMI_TEST_IMAGE_404_RATE", 0.0)
        self.transient_error_rate = self._parse_rate(
            "AMI_TEST_TRANSIENT_ERROR_RATE", 0.0
        )

        # Parse permanent error images
        permanent_images_str = os.getenv("AMI_TEST_PERMANENT_ERROR_IMAGES", "")
        self.permanent_error_images: Set[str] = set()
        if permanent_images_str:
            self.permanent_error_images = {
                img.strip() for img in permanent_images_str.split(",") if img.strip()
            }

        if not self.enabled:
            logger.info("Fault injection disabled")
            return

        logger.warning(
            f"🧨 FAULT INJECTION ENABLED 🧨 - "
            f"Worker crash: {self.worker_crash_rate:.1%}, "
            f"Network error: {self.network_error_rate:.1%}, "
            f"Corrupt image: {self.corrupt_image_rate:.1%}, "
            f"Image 404: {self.image_404_rate:.1%}, "
            f"Transient error: {self.transient_error_rate:.1%}, "
            f"Permanent error images: {len(self.permanent_error_images)}"
        )

    def _parse_rate(self, env_var: str, default: float) -> float:
        """Parse error rate from environment variable."""
        try:
            rate = float(os.getenv(env_var, str(default)))
            if not 0.0 <= rate <= 1.0:
                logger.error(
                    f"Invalid rate for {env_var}: {rate}. Must be between 0.0 and 1.0"
                )
                return default
            return rate
        except ValueError:
            logger.error(
                f"Invalid rate format for {env_var}: {os.getenv(env_var)}. Using default: {default}"
            )
            return default

    def _should_trigger(self, rate: float) -> bool:
        """Check if an error should trigger based on probability."""
        return self.enabled and random.random() < rate

    def maybe_crash_worker(self, context: str = "Unknown operation") -> None:
        """Randomly crash the worker process.

        Args:
            context: Description of what the worker was doing when it crashed
        """
        if self._should_trigger(self.worker_crash_rate):
            logger.error(f"💥 SIMULATED WORKER CRASH during: {context}")
            sys.exit(1)  # Simulate worker crash

    def maybe_network_error(self, operation: str = "API call") -> bool:
        """Check if a network error should be simulated.

        Args:
            operation: Description of the network operation

        Returns:
            True if a network error should be raised
        """
        if self._should_trigger(self.network_error_rate):
            logger.error(f"🌐 SIMULATED NETWORK ERROR during: {operation}")
            return True
        return False

    def maybe_image_404(self, image_url: str) -> bool:
        """Check if an image should return 404 Not Found.

        Args:
            image_url: The URL or identifier of the image

        Returns:
            True if a 404 error should be raised
        """
        # Check permanent error list first
        if self._is_permanent_error_image(image_url):
            logger.error(f"📷 PERMANENT IMAGE ERROR (404) for: {image_url}")
            return True

        if self._should_trigger(self.image_404_rate):
            logger.error(f"📷 SIMULATED IMAGE 404 for: {image_url}")
            return True
        return False

    def maybe_corrupt_image(self, image_url: str) -> bool:
        """Check if an image should be corrupted.

        Args:
            image_url: The URL or identifier of the image

        Returns:
            True if the image should be corrupted
        """
        # Check permanent error list first
        if self._is_permanent_error_image(image_url):
            logger.error(f"📷 PERMANENT IMAGE ERROR (corrupt) for: {image_url}")
            return True

        if self._should_trigger(self.corrupt_image_rate):
            logger.error(f"📷 SIMULATED CORRUPT IMAGE for: {image_url}")
            return True
        return False

    def maybe_transient_error(self, operation: str = "Operation") -> bool:
        """Check if a transient error should be simulated.

        Transient errors are temporary failures that should cause tasks to be
        re-queued for retry (vs permanent errors that should be reported as failed).

        Args:
            operation: Description of the operation that failed

        Returns:
            True if a transient error should be raised
        """
        if self._should_trigger(self.transient_error_rate):
            logger.error(f"⚡ SIMULATED TRANSIENT ERROR during: {operation}")
            return True
        return False

    def _is_permanent_error_image(self, image_url: str) -> bool:
        """Check if an image is in the permanent error list."""
        if not self.enabled or not self.permanent_error_images:
            return False

        # Check both full URL and just the filename
        filename = image_url.split("/")[-1] if "/" in image_url else image_url
        return (
            image_url in self.permanent_error_images
            or filename in self.permanent_error_images
        )

    def raise_network_error(self, operation: str = "API call") -> None:
        """Raise a simulated network error.

        Args:
            operation: Description of the network operation that failed
        """
        error_types = [
            requests.exceptions.ConnectionError(
                f"Simulated connection error during {operation}"
            ),
            requests.exceptions.Timeout(f"Simulated timeout during {operation}"),
            requests.exceptions.HTTPError(
                f"Simulated HTTP 500 error during {operation}"
            ),
        ]
        raise random.choice(error_types)

    def raise_image_error(self, image_url: str, error_type: str = "404") -> None:
        """Raise a simulated image loading error.

        Args:
            image_url: The URL of the image that failed
            error_type: Type of error ("404", "corrupt", "timeout")
        """
        if error_type == "404":
            response = requests.Response()
            response.status_code = 404
            raise requests.exceptions.HTTPError("404 Not Found", response=response)
        elif error_type == "corrupt":
            raise ValueError(f"Simulated corrupt image data for {image_url}")
        elif error_type == "timeout":
            raise requests.exceptions.Timeout(
                f"Simulated timeout downloading {image_url}"
            )
        else:
            raise RuntimeError(f"Simulated unknown error for image {image_url}")

    def get_corrupt_image_data(self) -> bytes:
        """Return invalid image data for corruption simulation."""
        return b"CORRUPT_IMAGE_DATA_NOT_VALID_JPEG_OR_PNG"

    def log_statistics(self) -> None:
        """Log current fault injection statistics."""
        if not self.enabled:
            logger.info("Fault injection is disabled")
            return

        logger.info(
            f"Fault injection rates - "
            f"Worker crash: {self.worker_crash_rate:.1%}, "
            f"Network: {self.network_error_rate:.1%}, "
            f"Corrupt image: {self.corrupt_image_rate:.1%}, "
            f"Image 404: {self.image_404_rate:.1%}, "
            f"Transient: {self.transient_error_rate:.1%}, "
            f"Permanent images: {len(self.permanent_error_images)}"
        )


# Global instance for easy importing
fault_injector = FaultInjector()
