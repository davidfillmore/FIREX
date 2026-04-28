"""Region definitions for FIREX analyses."""
from dataclasses import dataclass


@dataclass(frozen=True)
class Region:
    name: str
    lon_min: float
    lon_max: float
    lat_min: float
    lat_max: float

    def contains(self, lat: float, lon: float) -> bool:
        return (
            self.lat_min <= lat <= self.lat_max
            and self.lon_min <= lon <= self.lon_max
        )


REGIONS: dict[str, Region] = {
    "pacific-northwest": Region(
        name="pacific-northwest",
        lon_min=-130.0,
        lon_max=-110.0,
        lat_min=42.0,
        lat_max=52.0,
    ),
    # SE Australia: VIC, TAS, NSW, ACT, SE QLD — the area worst-hit by the
    # 2019-2020 "Black Summer" bushfires (peak Dec 2019 – Jan 2020).
    "eastern-australia": Region(
        name="eastern-australia",
        lon_min=140.0,
        lon_max=154.0,
        lat_min=-44.0,
        lat_max=-25.0,
    ),
}
