"""Canadian Forest Fire Weather Index (FWI) System, computed in-house (pure functions, no I/O).

Equations of Van Wagner, C.E. 1987. *Development and structure of the Canadian Forest Fire Weather Index System.*
Canadian Forestry Service, Forestry Technical Report 35, Ottawa (equation numbers below are his), with the
numerically more accurate forms of Eqs. 12, 15 and 21 of Wang, Y., Anderson, K.R.
and Suddaby, R.M. 2015. *Updated source code for calculating fire danger indices in the Canadian Forest Fire Weather
Index System.* Information Report NOR-X-424, Canadian Forest Service, Edmonton. tests/test_weather.py replays their
Table 7 (49 days of sample input and output) to one decimal.

Inputs are the noon local standard time observations of one day: temperature °C, relative humidity %, wind speed
km/h at 10 m, and the rain of the previous 24 h in mm. Day-length factors: the 46° N table of Van Wagner (1987) for
latitudes above 30° N (all of Tunisia but its southern tip), the 20° N table of Lawson and Armitage (2008) between
10° and 30° N.
"""

import math
from dataclasses import dataclass
from enum import StrEnum

# Eq. 1 / 10 constant of Van Wagner (1987); with it Table 7 of Wang et al. (2015) is reproduced exactly (their
# later code uses 250 * 59.5 / 101 = 147.27723, which shifts the FFMC by about 0.1).
FFMC_COEFFICIENT = 147.2
# Standard start-up values (Van Wagner 1987; Lawson and Armitage 2008) when no earlier day is known.
STARTUP_FFMC, STARTUP_DMC, STARTUP_DC = 85.0, 6.0, 15.0

# Effective day-length factors by month (January first).
DMC_DAY_LENGTH_46N = (6.5, 7.5, 9.0, 12.8, 13.9, 13.9, 12.4, 10.9, 9.4, 8.0, 7.0, 6.0)
DMC_DAY_LENGTH_20N = (7.9, 8.4, 8.9, 9.5, 9.9, 10.2, 10.1, 9.7, 9.1, 8.6, 8.1, 7.8)
DC_DAY_LENGTH_NORTH = (-1.6, -1.6, -1.6, 0.9, 3.8, 5.8, 6.4, 5.0, 2.4, 0.4, -1.6, -1.6)


class FireDanger(StrEnum):
    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"
    VERY_HIGH = "very_high"
    EXTREME = "extreme"


# Lower FWI bound of each class, as used by the European Forest Fire Information System for the Mediterranean
# (EFFIS fire danger classes: low < 5.2, moderate < 11.2, high < 21.3, very high < 38.0, extreme ≥ 38.0).
DANGER_THRESHOLDS = ((38.0, FireDanger.EXTREME), (21.3, FireDanger.VERY_HIGH), (11.2, FireDanger.HIGH),
                     (5.2, FireDanger.MODERATE))  # fmt: skip
DANGER_RANK = {level: rank for rank, level in enumerate(FireDanger)}


@dataclass(frozen=True, slots=True)
class Codes:
    """Moisture codes carried from one day to the next."""

    ffmc: float = STARTUP_FFMC
    dmc: float = STARTUP_DMC
    dc: float = STARTUP_DC


@dataclass(frozen=True, slots=True)
class Indices:
    ffmc: float
    dmc: float
    dc: float
    isi: float
    bui: float
    fwi: float

    @property
    def codes(self) -> Codes:
        return Codes(self.ffmc, self.dmc, self.dc)

    @property
    def danger(self) -> FireDanger:
        return danger_class(self.fwi)

    def rounded(self) -> dict[str, float]:
        return {k: round(getattr(self, k), 1) for k in ("ffmc", "dmc", "dc", "isi", "bui", "fwi")}


def danger_class(fwi_value: float) -> FireDanger:
    for bound, level in DANGER_THRESHOLDS:
        if fwi_value >= bound:
            return level
    return FireDanger.LOW


def ffmc_to_moisture(ffmc_value: float) -> float:
    """Fine fuel moisture content, % of dry weight (Eq. 1)."""
    return FFMC_COEFFICIENT * (101.0 - ffmc_value) / (59.5 + ffmc_value)


def fine_fuel_moisture_code(ffmc_prev: float, temp: float, rh: float, wind: float, rain: float) -> float:
    """Eqs. 1–10."""
    mo = ffmc_to_moisture(ffmc_prev)
    if rain > 0.5:
        rf = rain - 0.5  # Eq. 2
        wetting = 42.5 * rf * math.exp(-100.0 / (251.0 - mo)) * (1.0 - math.exp(-6.93 / rf))  # Eq. 3a
        if mo > 150.0:
            wetting += 0.0015 * (mo - 150.0) ** 2 * math.sqrt(rf)  # Eq. 3b
        mo = min(mo + wetting, 250.0)
    drying_term = 0.18 * (21.1 - temp) * (1.0 - math.exp(-0.115 * rh))
    ed = 0.942 * rh**0.679 + 11.0 * math.exp((rh - 100.0) / 10.0) + drying_term  # Eq. 4
    ew = 0.618 * rh**0.753 + 10.0 * math.exp((rh - 100.0) / 10.0) + drying_term  # Eq. 5
    if mo > ed:
        ko = 0.424 * (1.0 - (rh / 100.0) ** 1.7) + 0.0694 * math.sqrt(wind) * (1.0 - (rh / 100.0) ** 8)  # Eq. 6a
        kd = ko * 0.581 * math.exp(0.0365 * temp)  # Eq. 6b
        m = ed + (mo - ed) * 10.0 ** (-kd)  # Eq. 8
    elif mo < ew:
        dry = (100.0 - rh) / 100.0
        k1 = 0.424 * (1.0 - dry**1.7) + 0.0694 * math.sqrt(wind) * (1.0 - dry**8)  # Eq. 7a
        kw = k1 * 0.581 * math.exp(0.0365 * temp)  # Eq. 7b
        m = ew - (ew - mo) * 10.0 ** (-kw)  # Eq. 9
    else:
        m = mo
    return float(min(max(59.5 * (250.0 - m) / (FFMC_COEFFICIENT + m), 0.0), 101.0))  # Eq. 10


def duff_moisture_code(dmc_prev: float, temp: float, rh: float, rain: float, month: int, lat: float = 36.0) -> float:
    """Eqs. 11–16."""
    table = DMC_DAY_LENGTH_46N if lat > 30.0 else DMC_DAY_LENGTH_20N
    temp = max(temp, -1.1)
    drying = 1.894 * (temp + 1.1) * (100.0 - rh) * table[month - 1] * 1e-4  # Eq. 16 (100 K)
    po = dmc_prev
    if rain > 1.5:
        re = 0.92 * rain - 1.27  # Eq. 11
        mo = 20.0 + 280.0 / math.exp(0.023 * po)  # Eq. 12 (Wang et al. 2015 form)
        if po <= 33.0:
            b = 100.0 / (0.5 + 0.3 * po)  # Eq. 13a
        elif po <= 65.0:
            b = 14.0 - 1.3 * math.log(po)  # Eq. 13b
        else:
            b = 6.2 * math.log(po) - 17.2  # Eq. 13c
        mr = mo + 1000.0 * re / (48.77 + b * re)  # Eq. 14
        po = max(43.43 * (5.6348 - math.log(mr - 20.0)), 0.0)  # Eq. 15
    return max(po + drying, 0.0)


def drought_code(dc_prev: float, temp: float, rain: float, month: int) -> float:
    """Eqs. 17–23 (northern hemisphere day lengths)."""
    temp = max(temp, -2.8)
    evaporation = max((0.36 * (temp + 2.8) + DC_DAY_LENGTH_NORTH[month - 1]) / 2.0, 0.0)  # Eq. 22, halved (Eq. 23)
    do = dc_prev
    if rain > 2.8:
        rd = 0.83 * rain - 1.27  # Eq. 18
        qo = 800.0 * math.exp(-do / 400.0)  # Eq. 19
        do = max(do - 400.0 * math.log(1.0 + 3.937 * rd / qo), 0.0)  # Eqs. 20–21 combined
    return max(do + evaporation, 0.0)


def initial_spread_index(ffmc_value: float, wind: float) -> float:
    """Eqs. 24–26."""
    m = ffmc_to_moisture(ffmc_value)
    f_wind = math.exp(0.05039 * wind)  # Eq. 24
    f_fuel = 91.9 * math.exp(-0.1386 * m) * (1.0 + m**5.31 / 4.93e7)  # Eq. 25
    return float(0.208 * f_wind * f_fuel)  # Eq. 26


def buildup_index(dmc_value: float, dc_value: float) -> float:
    """Eqs. 27a–27b."""
    if dmc_value == 0.0 and dc_value == 0.0:
        return 0.0
    if dmc_value <= 0.4 * dc_value:
        u = 0.8 * dmc_value * dc_value / (dmc_value + 0.4 * dc_value)  # Eq. 27a
    else:
        u = dmc_value - (1.0 - 0.8 * dc_value / (dmc_value + 0.4 * dc_value)) * (
            0.92 + (0.0114 * dmc_value) ** 1.7
        )  # Eq. 27b
    return max(u, 0.0)


def fire_weather_index(isi: float, bui: float) -> float:
    """Eqs. 28–30."""
    if bui <= 80.0:
        f_d = 0.626 * bui**0.809 + 2.0  # Eq. 28a
    else:
        f_d = 1000.0 / (25.0 + 108.64 * math.exp(-0.023 * bui))  # Eq. 28b
    b = 0.1 * isi * f_d  # Eq. 29
    if b > 1.0:
        return math.exp(2.72 * (0.434 * math.log(b)) ** 0.647)  # Eq. 30a
    return float(b)  # Eq. 30b


def daily(previous: Codes, temp: float, rh: float, wind: float, rain: float, month: int, lat: float = 36.0) -> Indices:
    """One day of the system from yesterday's codes and today's noon weather (rain: 24 h to noon)."""
    rh = min(max(rh, 0.0), 100.0)
    wind, rain = max(wind, 0.0), max(rain, 0.0)
    ffmc = fine_fuel_moisture_code(previous.ffmc, temp, rh, wind, rain)
    dmc = duff_moisture_code(previous.dmc, temp, rh, rain, month, lat)
    dc = drought_code(previous.dc, temp, rain, month)
    isi = initial_spread_index(ffmc, wind)
    bui = buildup_index(dmc, dc)
    return Indices(ffmc=ffmc, dmc=dmc, dc=dc, isi=isi, bui=bui, fwi=fire_weather_index(isi, bui))
