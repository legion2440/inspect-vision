"""Validation and normalization for Bayes-PFL product/category context."""

from __future__ import annotations

import re


PRODUCT_PATTERN = re.compile(r"^[a-z]+(?:[ -][a-z]+)*$")


class ProductNameValidationError(ValueError):
    """Raised when a guided product/category value is missing or malformed."""


def normalize_product_name(value: str | None) -> str:
    normalized = " ".join(str(value or "").strip().replace("_", " ").split()).lower()
    if not normalized:
        raise ProductNameValidationError("Product / category is required for Bayes-PFL")
    if not 2 <= len(normalized) <= 40:
        raise ProductNameValidationError("Product / category must be between 2 and 40 characters")
    if len(normalized.split()) > 3:
        raise ProductNameValidationError("Product / category must contain at most 3 words")
    if PRODUCT_PATTERN.fullmatch(normalized) is None:
        raise ProductNameValidationError(
            "Product / category may contain only Latin letters, spaces, hyphens, or underscores"
        )
    return normalized
