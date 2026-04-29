"""Typed and validated configuration models for the weatheryear module."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import yaml


class ConfigValidationError(ValueError):
    """Raised when a weather-year configuration is missing required fields."""


def _expect_dict(raw: Any, context: str) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise ConfigValidationError(f"{context} must be a mapping, got {type(raw).__name__}")
    return raw


def _require(raw: dict[str, Any], key: str, context: str) -> Any:
    if key not in raw:
        raise ConfigValidationError(f"Missing required key '{key}' in {context}")
    return raw[key]


def _expect_list_of_str(value: Any, context: str) -> list[str]:
    if not isinstance(value, list) or not all(isinstance(v, str) for v in value):
        raise ConfigValidationError(f"{context} must be a list[str]")
    return value


def _expect_dict_of_list_str(value: Any, context: str) -> dict[str, list[str]]:
    value = _expect_dict(value, context)
    out: dict[str, list[str]] = {}
    for k, v in value.items():
        if not isinstance(k, str):
            raise ConfigValidationError(f"{context} keys must be strings")
        out[k] = _expect_list_of_str(v, f"{context}['{k}']")
    return out


def _load_yaml_file(config_fn: str) -> dict[str, Any]:
    with open(config_fn) as file:
        raw = yaml.safe_load(file)
    return _expect_dict(raw, "root config")


@dataclass(frozen=True)
class CapDevTimestepsConfig:
    s: str
    t: list[str]

    @classmethod
    def from_raw(cls, raw: Any) -> "CapDevTimestepsConfig":
        raw = _expect_dict(raw, "CapDev_timesteps_to_keep")
        s = _require(raw, "S", "CapDev_timesteps_to_keep")
        t = _require(raw, "T", "CapDev_timesteps_to_keep")
        if not isinstance(s, str):
            raise ConfigValidationError("CapDev_timesteps_to_keep['S'] must be a string")
        return cls(s=s, t=_expect_list_of_str(t, "CapDev_timesteps_to_keep['T']"))

    def as_legacy_dict(self) -> dict[str, Any]:
        return {"CapDev_timesteps_to_keep": {"S": self.s, "T": self.t}}


@dataclass(frozen=True)
class RegionsConfig:
    onshore: list[str]
    offshore: list[str]

    @classmethod
    def from_raw(cls, raw: Any) -> "RegionsConfig":
        raw = _expect_dict(raw, "Regions_to_keep")
        onshore = _expect_list_of_str(_require(raw, "onshore", "Regions_to_keep"), "Regions_to_keep['onshore']")
        offshore = _expect_list_of_str(_require(raw, "offshore", "Regions_to_keep"), "Regions_to_keep['offshore']")
        return cls(onshore=onshore, offshore=offshore)


@dataclass(frozen=True)
class AnnuityCalculationConfig:
    debt_share: float
    discount_rate: float
    interest_rate: float

    @classmethod
    def from_raw(cls, raw: Any) -> "AnnuityCalculationConfig":
        raw = _expect_dict(raw, "ANNUITYCG_calculation")
        debt = _require(raw, "DEBT_SHARE", "ANNUITYCG_calculation")
        discount = _require(raw, "DISCOUNTRATE", "ANNUITYCG_calculation")
        interest = _require(raw, "INTEREST_RATE", "ANNUITYCG_calculation")
        try:
            return cls(float(debt), float(discount), float(interest))
        except (TypeError, ValueError) as exc:
            raise ConfigValidationError("ANNUITYCG_calculation values must be numeric") from exc


@dataclass(frozen=True)
class DemandModuleConfig:
    spaceheat_to_hotwater_ratio: float
    ann_corr_fac_ref_year: int
    demand_model_results: str
    capdev_timesteps_to_keep: CapDevTimestepsConfig

    @classmethod
    def from_file(cls, config_fn: str) -> "DemandModuleConfig":
        raw = _load_yaml_file(config_fn)
        ratio = _require(raw, "spaceHeat_to_hotWater_ratio", "root config")
        ref_year = _require(raw, "ann_corr_fac_ref_year", "root config")
        demand_results = _require(raw, "demand_model_results", "root config")
        if not isinstance(demand_results, str):
            raise ConfigValidationError("demand_model_results must be a string")
        try:
            ratio_value = float(ratio)
            ref_year_value = int(ref_year)
        except (TypeError, ValueError) as exc:
            raise ConfigValidationError("spaceHeat_to_hotWater_ratio and ann_corr_fac_ref_year must be numeric") from exc
        return cls(
            spaceheat_to_hotwater_ratio=ratio_value,
            ann_corr_fac_ref_year=ref_year_value,
            demand_model_results=demand_results,
            capdev_timesteps_to_keep=CapDevTimestepsConfig.from_raw(
                _require(raw, "CapDev_timesteps_to_keep", "root config")
            ),
        )


@dataclass(frozen=True)
class ToBalmorelConfig:
    capdev_timesteps_to_keep: CapDevTimestepsConfig

    @classmethod
    def from_file(cls, config_fn: str) -> "ToBalmorelConfig":
        raw = _load_yaml_file(config_fn)
        return cls(
            capdev_timesteps_to_keep=CapDevTimestepsConfig.from_raw(
                _require(raw, "CapDev_timesteps_to_keep", "root config")
            )
        )


@dataclass(frozen=True)
class WeatherYearConfig:
    corres_results: dict[str, list[str]]
    regions_to_keep: RegionsConfig
    rg_to_keep: dict[str, list[str]]
    turbine_to_keep: list[str]
    tech_to_keep: list[str]

    @classmethod
    def from_file(cls, config_fn: str) -> "WeatherYearConfig":
        raw = _load_yaml_file(config_fn)
        corres_results = _expect_dict_of_list_str(
            _require(raw, "corres_results", "root config"),
            "corres_results",
        )
        required_sources = {"wind", "solar"}
        missing_sources = required_sources - set(corres_results.keys())
        if missing_sources:
            raise ConfigValidationError(
                f"corres_results is missing required source keys: {sorted(missing_sources)}"
            )

        return cls(
            corres_results=corres_results,
            regions_to_keep=RegionsConfig.from_raw(_require(raw, "Regions_to_keep", "root config")),
            rg_to_keep=_expect_dict_of_list_str(_require(raw, "RGs_to_keep", "root config"), "RGs_to_keep"),
            turbine_to_keep=_expect_list_of_str(_require(raw, "turbine_to_keep", "root config"), "turbine_to_keep"),
            tech_to_keep=_expect_list_of_str(_require(raw, "tech_to_keep", "root config"), "tech_to_keep"),
        )

    def regions_for_source(self, source: str) -> list[str]:
        if source == "offshore":
            return self.regions_to_keep.offshore
        if source == "onshore":
            return self.regions_to_keep.onshore
        if source == "all":
            return self.regions_to_keep.onshore + self.regions_to_keep.offshore
        raise ConfigValidationError(f"Unsupported region source: {source}")


@dataclass(frozen=True)
class AdditionalIncConfig:
    regions_to_keep: RegionsConfig
    rg_to_keep: dict[str, list[str]]
    turbine_to_keep: list[str]
    annuitycg_calculation: AnnuityCalculationConfig
    vre_potentials: str
    vre_tech_costs: str
    existing_wind_cap: str
    existing_solar_cap: str

    @classmethod
    def from_file(cls, config_fn: str) -> "AdditionalIncConfig":
        raw = _load_yaml_file(config_fn)
        vre_potentials = _require(raw, "VRE_potentials", "root config")
        vre_tech_costs = _require(raw, "VRE_tech_costs", "root config")
        existing_wind_cap = _require(raw, "Existing_wind_cap", "root config")
        existing_solar_cap = _require(raw, "Existing_solar_cap", "root config")
        for key, value in {
            "VRE_potentials": vre_potentials,
            "VRE_tech_costs": vre_tech_costs,
            "Existing_wind_cap": existing_wind_cap,
            "Existing_solar_cap": existing_solar_cap,
        }.items():
            if not isinstance(value, str):
                raise ConfigValidationError(f"{key} must be a string")

        return cls(
            regions_to_keep=RegionsConfig.from_raw(_require(raw, "Regions_to_keep", "root config")),
            rg_to_keep=_expect_dict_of_list_str(_require(raw, "RGs_to_keep", "root config"), "RGs_to_keep"),
            turbine_to_keep=_expect_list_of_str(_require(raw, "turbine_to_keep", "root config"), "turbine_to_keep"),
            annuitycg_calculation=AnnuityCalculationConfig.from_raw(
                _require(raw, "ANNUITYCG_calculation", "root config")
            ),
            vre_potentials=vre_potentials,
            vre_tech_costs=vre_tech_costs,
            existing_wind_cap=existing_wind_cap,
            existing_solar_cap=existing_solar_cap,
        )

    def rgs_for(self, tech: str) -> list[str]:
        if tech not in self.rg_to_keep:
            raise ConfigValidationError(f"Missing RGs_to_keep entry for technology: {tech}")
        return self.rg_to_keep[tech]

    def as_legacy_dict(self) -> dict[str, Any]:
        return {
            "Regions_to_keep": {
                "onshore": self.regions_to_keep.onshore,
                "offshore": self.regions_to_keep.offshore,
            },
            "RGs_to_keep": self.rg_to_keep,
            "turbine_to_keep": self.turbine_to_keep,
            "ANNUITYCG_calculation": {
                "DEBT_SHARE": self.annuitycg_calculation.debt_share,
                "DISCOUNTRATE": self.annuitycg_calculation.discount_rate,
                "INTEREST_RATE": self.annuitycg_calculation.interest_rate,
            },
            "VRE_potentials": self.vre_potentials,
            "VRE_tech_costs": self.vre_tech_costs,
            "Existing_wind_cap": self.existing_wind_cap,
            "Existing_solar_cap": self.existing_solar_cap,
        }
