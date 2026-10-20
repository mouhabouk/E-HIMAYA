"""Surface fire spread: Rothermel (1972) with the 13 Anderson fuel models and an elliptical fire shape (pure functions).

References (equation forms as compiled in Andrews, P.L. 2018. *The Rothermel surface fire spread model and associated
developments: A comprehensive explanation.* Gen. Tech. Rep. RMRS-GTR-371, USDA Forest Service, Tables 3 and 6):

* Rothermel, R.C. 1972. *A mathematical model for predicting fire spread in wildland fuels.* Res. Pap. INT-115.
* Albini, F.A. 1976. *Estimating wildfire behavior and effects.* Gen. Tech. Rep. INT-30 (size-class weighting, live
  fuel moisture of extinction).
* Anderson, H.E. 1982. *Aids to determining fuel models for estimating fire behavior.* Gen. Tech. Rep. INT-122
  (the 13 fuel models and their reference spread rates, replayed in tests/test_forecast.py).
* Anderson, H.E. 1983. *Predicting wind-driven wild land fire size and shape.* Res. Pap. INT-305 (length-to-breadth
  ratio of the ellipse).
* Rothermel, R.C. 1983. *How to predict the spread and intensity of forest and range fires.* Gen. Tech. Rep. INT-143
  (vector sum of wind and slope effects).
* Andrews, P.L., Cruz, M.G., Rothermel, R.C. 2013. *Examination of the wind speed limit function in the Rothermel
  surface fire spread model.* International Journal of Wildland Fire 22: 959–969 (wind limit used here).

Internally in the model's original English units (lb, ft, Btu, min); results converted to SI.
"""

import math
from dataclasses import dataclass, field

TONS_PER_ACRE = 2000.0 / 43560.0  # → lb/ft²
FT_PER_M = 1.0 / 0.3048
MPH_TO_FT_MIN = 88.0
KMH_TO_MPH = 1.0 / 1.609344
PARTICLE_DENSITY = 32.0  # lb/ft³
HEAT_CONTENT = 8000.0  # Btu/lb
TOTAL_MINERAL = 0.0555
EFFECTIVE_MINERAL = 0.010
SAV_10H, SAV_100H = 109.0, 30.0
MAX_LENGTH_TO_BREADTH = 8.0
# Albini (1976) size-class bins (by surface-area-to-volume ratio, 1/ft) used to weight net fuel loads.
_SAV_BINS = (1200.0, 192.0, 96.0, 48.0, 16.0)


@dataclass(frozen=True, slots=True)
class FuelModel:
    number: int
    name: str
    # Loads in tons/acre: dead 1-h, 10-h, 100-h; live herbaceous, live woody.
    load_1h: float
    load_10h: float
    load_100h: float
    load_herb: float
    load_woody: float
    sav_1h: float  # 1/ft
    sav_live: float  # 1/ft (herbaceous and woody share it in the 13 models)
    depth_ft: float
    mx_dead: float  # dead fuel moisture of extinction, fraction
    # Wind adjustment factor (20-ft wind → midflame) for unsheltered fuel, Andrews (2012, RMRS-GTR-266, table 2).
    waf: float


# Anderson (1982), as tabulated in Andrews (2018, table 8a).
FUEL_MODELS: dict[int, FuelModel] = {
    m.number: m
    for m in (
        FuelModel(1, "short grass", 0.74, 0.0, 0.0, 0.0, 0.0, 3500, 1500, 1.0, 0.12, 0.36),
        FuelModel(2, "timber grass and understory", 2.0, 1.0, 0.5, 0.5, 0.0, 3000, 1500, 1.0, 0.15, 0.36),
        FuelModel(3, "tall grass", 3.01, 0.0, 0.0, 0.0, 0.0, 1500, 1500, 2.5, 0.25, 0.44),
        FuelModel(4, "chaparral", 5.01, 4.01, 2.0, 0.0, 5.01, 2000, 1500, 6.0, 0.20, 0.55),
        FuelModel(5, "brush", 1.0, 0.5, 0.0, 0.0, 2.0, 2000, 1500, 2.0, 0.20, 0.42),
        FuelModel(6, "dormant brush, hardwood slash", 1.5, 2.5, 2.0, 0.0, 0.0, 1750, 1500, 2.5, 0.25, 0.44),
        FuelModel(7, "southern rough", 1.13, 1.87, 1.5, 0.0, 0.37, 1750, 1500, 2.5, 0.40, 0.44),
        FuelModel(8, "short needle litter", 1.5, 1.0, 2.5, 0.0, 0.0, 2000, 1500, 0.2, 0.30, 0.28),
        FuelModel(9, "long needle or hardwood litter", 2.92, 0.41, 0.15, 0.0, 0.0, 2500, 1500, 0.2, 0.25, 0.28),
        FuelModel(10, "timber litter and understory", 3.01, 2.0, 5.01, 0.0, 2.0, 2000, 1500, 1.0, 0.25, 0.36),
        FuelModel(11, "light logging slash", 1.5, 4.51, 5.51, 0.0, 0.0, 1500, 1500, 1.0, 0.15, 0.36),
        FuelModel(12, "medium logging slash", 4.01, 14.03, 16.53, 0.0, 0.0, 1500, 1500, 2.3, 0.20, 0.43),
        FuelModel(13, "heavy logging slash", 7.01, 23.04, 28.05, 0.0, 0.0, 1500, 1500, 3.0, 0.25, 0.46),
    )
}


@dataclass(frozen=True, slots=True)
class Moisture:
    """Fuel moisture contents, fractions of dry weight."""

    dead_1h: float
    dead_10h: float
    dead_100h: float
    live_herb: float = 1.0
    live_woody: float = 1.0


@dataclass(frozen=True, slots=True)
class _Particle:
    load: float  # lb/ft²
    sav: float
    moisture: float


@dataclass(frozen=True, slots=True)
class Spread:
    """Fire behaviour in the direction of maximum spread."""

    ros_ft_min: float  # head fire rate of spread
    ros_no_wind_ft_min: float
    reaction_intensity: float  # Btu/ft²/min
    heading_deg: float  # direction of maximum spread (towards), degrees clockwise from north
    effective_wind_mph: float
    length_to_breadth: float
    backing_ros_ft_min: float
    sav: float  # characteristic surface-area-to-volume ratio, 1/ft
    bulk_density: float  # lb/ft³
    packing_ratio: float
    relative_packing_ratio: float
    wind_limited: bool
    notes: list[str] = field(default_factory=list)

    @property
    def ros_m_min(self) -> float:
        return self.ros_ft_min * 0.3048

    @property
    def backing_m_min(self) -> float:
        return self.backing_ros_ft_min * 0.3048

    @property
    def fireline_intensity_kw_m(self) -> float:
        """Byram's intensity at the head, kW/m (residence time 384/σ min, Anderson 1969)."""
        residence_min = 384.0 / self.sav
        btu_ft_s = self.reaction_intensity * residence_min * self.ros_ft_min / 60.0
        return btu_ft_s * 3.4613

    @property
    def flame_length_m(self) -> float:
        """Byram (1959) flame length from the fireline intensity."""
        return float(0.0775 * self.fireline_intensity_kw_m**0.46)


def _bin(sav: float) -> int:
    return next((i for i, bound in enumerate(_SAV_BINS) if sav >= bound), len(_SAV_BINS))


def _category(particles: list[_Particle]) -> tuple[float, float, list[float]] | None:
    """Surface area, characteristic SAV and per-particle area weights of one category (dead or live)."""
    areas = [p.sav * p.load / PARTICLE_DENSITY for p in particles]
    total = sum(areas)
    if total <= 0:
        return None
    weights = [a / total for a in areas]
    return total, sum(w * p.sav for w, p in zip(weights, particles, strict=True)), weights


def _net_load(particles: list[_Particle], weights: list[float]) -> float:
    """Albini (1976): loads weighted by the area share of their size class within the category."""
    bins: dict[int, float] = {}
    for w, p in zip(weights, particles, strict=True):
        bins[_bin(p.sav)] = bins.get(_bin(p.sav), 0.0) + w
    return sum(bins[_bin(p.sav)] * p.load * (1.0 - TOTAL_MINERAL) for p in particles)


def _damping(moisture: float, extinction: float) -> float:
    if extinction <= 0 or moisture >= extinction:
        return 0.0  # at or above the moisture of extinction the fuel does not burn (the polynomial is 0 at 1)
    ratio = moisture / extinction
    return max(1.0 - 2.59 * ratio + 5.11 * ratio**2 - 3.52 * ratio**3, 0.0)


def length_to_breadth(effective_wind_mph: float) -> float:
    """Anderson (1983): L/B = 0.936 e^(0.2566 U) + 0.461 e^(-0.1548 U) - 0.397, U midflame wind in mi/h, capped at
    8 as in FARSITE (Finney 1998) beyond the range of Anderson's data."""
    u = max(effective_wind_mph, 0.0)
    return min(max(0.936 * math.exp(0.2566 * u) + 0.461 * math.exp(-0.1548 * u) - 0.397, 1.0), MAX_LENGTH_TO_BREADTH)


def spread(
    model: FuelModel,
    moisture: Moisture,
    midflame_wind_mph: float,
    wind_towards_deg: float = 0.0,
    slope_fraction: float = 0.0,
    upslope_deg: float = 0.0,
    *,
    wind_limit: bool = True,
) -> Spread:
    """Rothermel (1972) rate of spread with wind and slope combined as vectors (Rothermel 1983)."""
    t = TONS_PER_ACRE
    dead = [
        _Particle(model.load_1h * t, model.sav_1h, moisture.dead_1h),
        _Particle(model.load_10h * t, SAV_10H, moisture.dead_10h),
        _Particle(model.load_100h * t, SAV_100H, moisture.dead_100h),
    ]
    live = [
        _Particle(model.load_herb * t, model.sav_live, moisture.live_herb),
        _Particle(model.load_woody * t, model.sav_live, moisture.live_woody),
    ]
    dead = [p for p in dead if p.load > 0]
    live = [p for p in live if p.load > 0]
    dead_cat, live_cat = _category(dead), _category(live)
    assert dead_cat is not None, "every Anderson model has dead fuel"
    area_dead = dead_cat[0]
    area_live = live_cat[0] if live_cat else 0.0
    area_total = area_dead + area_live
    f_dead, f_live = area_dead / area_total, area_live / area_total
    sigma = f_dead * dead_cat[1] + (f_live * live_cat[1] if live_cat else 0.0)

    total_load = sum(p.load for p in dead + live)
    bulk_density = total_load / model.depth_ft
    beta = bulk_density / PARTICLE_DENSITY
    beta_op = 3.348 * sigma**-0.8189
    relative = beta / beta_op
    a = 133.0 * sigma**-0.7913
    gamma_max = sigma**1.5 / (495.0 + 0.0594 * sigma**1.5)
    gamma = gamma_max * relative**a * math.exp(a * (1.0 - relative))
    eta_s = min(0.174 * EFFECTIVE_MINERAL**-0.19, 1.0)

    # Moisture of the dead category and live moisture of extinction (Albini 1976).
    dead_weights = dead_cat[2]
    m_dead = sum(w * p.moisture for w, p in zip(dead_weights, dead, strict=True))
    reaction = gamma * _net_load(dead, dead_weights) * HEAT_CONTENT * _damping(m_dead, model.mx_dead) * eta_s
    notes: list[str] = []
    if live_cat is not None:
        live_weights = live_cat[2]
        m_live = sum(w * p.moisture for w, p in zip(live_weights, live, strict=True))
        fine_dead = sum(p.load * math.exp(-138.0 / p.sav) for p in dead)
        fine_live = sum(p.load * math.exp(-500.0 / p.sav) for p in live)
        fine_dead_moisture = sum(p.load * math.exp(-138.0 / p.sav) * p.moisture for p in dead) / fine_dead
        mx_live = max(2.9 * (fine_dead / fine_live) * (1.0 - fine_dead_moisture / model.mx_dead) - 0.226, model.mx_dead)
        reaction += gamma * _net_load(live, live_weights) * HEAT_CONTENT * _damping(m_live, mx_live) * eta_s

    xi = math.exp((0.792 + 0.681 * sigma**0.5) * (beta + 0.1)) / (192.0 + 0.2595 * sigma)
    heat_sink = 0.0
    for fraction, particles, weights in ((f_dead, dead, dead_weights), (f_live, live, live_cat[2] if live_cat else [])):
        for w, p in zip(weights, particles, strict=True):
            heat_sink += fraction * w * math.exp(-138.0 / p.sav) * (250.0 + 1116.0 * p.moisture)
    heat_sink *= bulk_density
    r0 = reaction * xi / heat_sink if heat_sink > 0 else 0.0

    c = 7.47 * math.exp(-0.133 * sigma**0.55)
    b = 0.02526 * sigma**0.54
    e = 0.715 * math.exp(-3.59e-4 * sigma)
    wind_ft_min = max(midflame_wind_mph, 0.0) * MPH_TO_FT_MIN
    limited = False
    if wind_limit:
        # Andrews et al. (2013): U_lim = 96.8 I_R^(1/3) ft/min replaces Rothermel's 0.9 I_R.
        limit = 96.8 * reaction ** (1.0 / 3.0)
        if wind_ft_min > limit:
            wind_ft_min, limited = limit, True
            notes.append("wind_limit_applied")
    phi_w = c * wind_ft_min**b * relative**-e if wind_ft_min > 0 else 0.0
    phi_s = 5.275 * beta**-0.3 * max(slope_fraction, 0.0) ** 2

    # Vector sum of the wind and slope effects (Rothermel 1983).
    wx = phi_w * math.sin(math.radians(wind_towards_deg)) + phi_s * math.sin(math.radians(upslope_deg))
    wy = phi_w * math.cos(math.radians(wind_towards_deg)) + phi_s * math.cos(math.radians(upslope_deg))
    phi_e = math.hypot(wx, wy)
    heading = (math.degrees(math.atan2(wx, wy)) + 360.0) % 360.0 if phi_e > 0 else wind_towards_deg % 360.0
    ros = r0 * (1.0 + phi_e)
    effective_ft_min = (phi_e * relative**e / c) ** (1.0 / b) if phi_e > 0 else 0.0
    effective_mph = effective_ft_min / MPH_TO_FT_MIN
    lb = length_to_breadth(effective_mph)
    ecc = math.sqrt(lb**2 - 1.0) / lb
    backing = ros * (1.0 - ecc) / (1.0 + ecc)
    return Spread(
        ros_ft_min=ros,
        ros_no_wind_ft_min=r0,
        reaction_intensity=reaction,
        heading_deg=heading,
        effective_wind_mph=effective_mph,
        length_to_breadth=lb,
        backing_ros_ft_min=backing,
        sav=sigma,
        bulk_density=bulk_density,
        packing_ratio=beta,
        relative_packing_ratio=relative,
        wind_limited=limited,
        notes=notes,
    )


def midflame_wind_mph(wind_10m_kmh: float, model: FuelModel, *, sheltered: float | None = None) -> float:
    """10-m wind → 20-ft wind (÷ 1.15, Lawson and Armitage 2008) → midflame wind (wind adjustment factor)."""
    waf = sheltered if sheltered is not None else model.waf
    return wind_10m_kmh * KMH_TO_MPH / 1.15 * waf


@dataclass(frozen=True, slots=True)
class Ellipse:
    """Fire perimeter after ``minutes``: an ellipse whose rear focus is the ignition point (Anderson 1983)."""

    minutes: float
    head_m: float  # ignition → head
    back_m: float  # ignition → back
    length_m: float
    width_m: float
    heading_deg: float

    @property
    def area_ha(self) -> float:
        return math.pi * (self.length_m / 2) * (self.width_m / 2) / 10_000.0

    def ring(self, lat: float, lon: float, vertices: int = 48) -> list[list[float]]:
        """Closed GeoJSON ring [[lon, lat], …] on a local tangent plane (accurate to well under 1 % at 10 km)."""
        a, b = self.length_m / 2, self.width_m / 2
        offset = (self.head_m - self.back_m) / 2  # ellipse centre, downwind of the ignition point
        theta = math.radians(self.heading_deg)
        m_per_deg_lat = 111_320.0
        m_per_deg_lon = 111_320.0 * math.cos(math.radians(lat))
        ring: list[list[float]] = []
        for i in range(vertices):
            t = 2 * math.pi * i / vertices
            along, across = offset + a * math.cos(t), b * math.sin(t)
            # "along" points to the heading (bearing theta), "across" 90° clockwise from it.
            east = along * math.sin(theta) + across * math.cos(theta)
            north = along * math.cos(theta) - across * math.sin(theta)
            ring.append([round(lon + east / m_per_deg_lon, 6), round(lat + north / m_per_deg_lat, 6)])
        ring.append(ring[0])
        return ring


def ellipse(result: Spread, minutes: float) -> Ellipse:
    head = result.ros_m_min * minutes
    back = result.backing_m_min * minutes
    length = head + back
    return Ellipse(
        minutes=minutes,
        head_m=head,
        back_m=back,
        length_m=length,
        width_m=length / result.length_to_breadth,
        heading_deg=result.heading_deg,
    )
