from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class Variant(str, Enum):
    VANILLA = "vanilla"
    EEA_ONLY = "eea_only"
    RETRY_WITHOUT_DIAGNOSIS = "retry_without_diagnosis"
    PACC = "pacc"


@dataclass(frozen=True)
class PACCSettings:
    """Public mode selection only; numerical settings remain outside this package."""
    variant: Variant

    def __post_init__(self) -> None:
        object.__setattr__(self, "variant", Variant(self.variant))

    @property
    def use_pta(self) -> bool:
        return self.variant in {Variant.PACC, Variant.RETRY_WITHOUT_DIAGNOSIS}
