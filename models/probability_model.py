"""Modelo de probabilidad de referencia — baseline lognormal.

P(S_T > K) asumiendo retornos lognormales sin drift (mediana martingala,
sin costo de carry). Es deliberadamente el modelo más simple defendible:
los edges grandes contra este modelo se tratan primero como sospecha de
error de modelo, no como ventaja (PRD §8).

Sin dependencias externas: usa math.erf en lugar de scipy.
"""
from __future__ import annotations

import math

SQRT2 = math.sqrt(2.0)
HOURS_PER_YEAR = 365.0 * 24.0


def norm_cdf(x: float) -> float:
    return 0.5 * (1.0 + math.erf(x / SQRT2))


def prob_above(spot: float, strike: float, vol: float, tte_years: float) -> float:
    """P(S_T > strike) con S_t lognormal, drift 0, vol anualizada.

    d = (ln(S/K) - 0.5*vol^2*T) / (vol*sqrt(T));  P = N(d)
    En el límite T->0 o vol->0 colapsa al indicador spot > strike.
    """
    if spot <= 0 or strike <= 0:
        raise ValueError("spot y strike deben ser positivos")
    if tte_years <= 0 or vol <= 0:
        return 1.0 if spot > strike else 0.0
    d = (math.log(spot / strike) - 0.5 * vol * vol * tte_years) / (vol * math.sqrt(tte_years))
    return norm_cdf(d)


def prob_below(spot: float, strike: float, vol: float, tte_years: float) -> float:
    return 1.0 - prob_above(spot, strike, vol, tte_years)


def tte_years_from_hours(tte_hours: float) -> float:
    return tte_hours / HOURS_PER_YEAR
