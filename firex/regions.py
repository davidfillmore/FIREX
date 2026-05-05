"""Region definitions for FIREX analyses.

The full registry includes regions slated for future analysis. Four are
*featured* — the story arc for the current presentation:

- pacific-northwest    (2017 / 2018 / 2020 / 2021 fire seasons)
- eastern-canada       (2023 Quebec/Ontario record boreal season)
- eastern-australia    (2019-20 Black Summer)
- eastern-siberia      (2019 / 2021 Yakutia megafires)

Featured regions render in orange on the region map; the others are
drawn in grey and pulled into the analysis pipeline only when added to
a config.
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class Region:
    name: str
    lon_min: float
    lon_max: float
    lat_min: float
    lat_max: float
    featured: bool = False
    description: str = ""

    def contains(self, lat: float, lon: float) -> bool:
        return (
            self.lat_min <= lat <= self.lat_max
            and self.lon_min <= lon <= self.lon_max
        )


REGIONS: dict[str, Region] = {
    # ── Featured (story arc) ──────────────────────────────────────────
    "pacific-northwest": Region(
        name="pacific-northwest",
        lon_min=-130.0, lon_max=-110.0, lat_min=42.0, lat_max=52.0,
        featured=True,
        description="2017 / 2018 / 2020 / 2021 fire seasons",
    ),
    "eastern-canada": Region(
        name="eastern-canada",
        lon_min=-90.0, lon_max=-65.0, lat_min=48.0, lat_max=58.0,
        featured=True,
        description="2023 Quebec/Ontario record boreal season; smoke into eastern US",
    ),
    "eastern-australia": Region(
        name="eastern-australia",
        lon_min=140.0, lon_max=154.0, lat_min=-44.0, lat_max=-25.0,
        featured=True,
        description="2019-20 Black Summer (VIC/TAS/NSW/ACT/SE-QLD)",
    ),
    "eastern-siberia": Region(
        name="eastern-siberia",
        lon_min=110.0, lon_max=155.0, lat_min=55.0, lat_max=72.0,
        featured=True,
        description="2019 / 2021 Yakutia megafires",
    ),

    # ── Future-analysis pool ──────────────────────────────────────────
    "western-canada": Region(
        name="western-canada",
        lon_min=-130.0, lon_max=-105.0, lat_min=52.0, lat_max=62.0,
        description="2023 NWT/BC record season; Yellowknife evacuation",
    ),
    "alaska": Region(
        name="alaska",
        lon_min=-165.0, lon_max=-141.0, lat_min=60.0, lat_max=72.0,
        description="2004 record season, 2022 boreal fires",
    ),
    "california": Region(
        name="california",
        lon_min=-124.0, lon_max=-114.0, lat_min=32.0, lat_max=42.0,
        description="2018 Camp; 2020 Creek and August Complex",
    ),
    "central-africa": Region(
        name="central-africa",
        lon_min=15.0, lon_max=35.0, lat_min=-15.0, lat_max=5.0,
        description="World's largest savanna biomass-burning region by area",
    ),
    "amazon": Region(
        name="amazon",
        lon_min=-75.0, lon_max=-50.0, lat_min=-15.0, lat_max=-5.0,
        description="Deforestation arc; 2019 / 2023 events",
    ),
    "maritime-se-asia": Region(
        name="maritime-se-asia",
        lon_min=95.0, lon_max=120.0, lat_min=-5.0, lat_max=5.0,
        description="Indonesian peat fires; 2015 ENSO event",
    ),
    "northern-australia": Region(
        name="northern-australia",
        lon_min=125.0, lon_max=145.0, lat_min=-20.0, lat_max=-10.0,
        description="Annual dry-season savanna burning",
    ),
    "mediterranean": Region(
        name="mediterranean",
        lon_min=-10.0, lon_max=30.0, lat_min=35.0, lat_max=45.0,
        description="Recurring Greece / Spain / Portugal fires",
    ),
}
