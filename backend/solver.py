"""
应力公式求解器模块
====================
求解竹纤维复合材料管壁在轴向受压状态下的一维波动方程与局部损伤演化。

控制方程 (含阻尼的一维波动方程):

    ∂²u/∂t² + 2β ∂u/∂t = c² ∂²u/∂x²

其中:
    u(x, t)  —— 轴向位移场
    c = √(E/ρ) —— 纵波波速
    β        —— 瑞利阻尼系数
    E        —— 竹纤维复合材料有效杨氏模量
    ρ        —— 材料密度

应变: ε(x, t) = ∂u/∂x
应力: σ(x, t) = E_eff(x, t) · ε(x, t)
有效模量: E_eff = E · (1 - D), D ∈ [0, 1] 为损伤变量

损伤演化 (应力阈值型):
    当等效应力 σ_eq > 损伤起始应力 σ_c0 时, 损伤按幂律累积:
        dD/dt = A · (σ_eq / σ_c0 - 1)^m
    D 上限为临界损伤 D_c, 超过即视为局部破坏。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict

import numpy as np


@dataclass
class MaterialParams:
    """竹纤维复合材料本构参数。"""

    young_modulus: float = 18.0e9
    density: float = 850.0
    damping: float = 0.0
    critical_stress: float = 25.0e6
    damage_rate: float = 8000.0
    damage_exponent: float = 1.5
    critical_damage: float = 0.85
    residual_modulus_ratio: float = 0.05

    def wave_speed(self) -> float:
        return float(np.sqrt(self.young_modulus / self.density))


@dataclass
class GeometryParams:
    """管壁几何与边界参数。"""

    length: float = 0.5
    n_nodes: int = 201
    load_velocity: float = 12.0
    total_time: float = 4.0e-4
    n_steps: int = 8000
    save_every: int = 16

    @property
    def dx(self) -> float:
        return self.length / (self.n_nodes - 1)

    @property
    def dt(self) -> float:
        return self.total_time / self.n_steps


@dataclass
class SimulationResult:
    """仿真结果容器, 存储各物理量的时空场。"""

    x: np.ndarray
    t: np.ndarray
    displacement: np.ndarray
    strain: np.ndarray
    stress: np.ndarray
    damage: np.ndarray
    effective_modulus: np.ndarray
    meta: Dict[str, float] = field(default_factory=dict)

    def summary(self) -> Dict[str, float]:
        return {
            "max_stress_MPa": float(np.max(np.abs(self.stress)) / 1.0e6),
            "max_strain": float(np.max(np.abs(self.strain))),
            "max_damage": float(np.max(self.damage)),
            "failed_nodes": int(np.sum(self.damage[-1] >= 0.85)),
            "mean_stress_MPa": float(np.mean(np.abs(self.stress)) / 1.0e6),
            "n_time_frames": int(self.stress.shape[0]),
            "n_spatial_nodes": int(self.stress.shape[1]),
        }


class BambooFiberSolver:
    """竹纤维复合材料管壁轴向受压波动-损伤耦合求解器。

    采用显式中心差分格式 (FDM) 求解阻尼波动方程, 在每个时间步内
    依据当前应力场更新损伤变量与有效模量, 实现波传-损伤耦合。
    """

    def __init__(
        self,
        material: MaterialParams | None = None,
        geometry: GeometryParams | None = None,
    ) -> None:
        self.material = material or MaterialParams()
        self.geometry = geometry or GeometryParams()
        self._validate_cfl()

    def _validate_cfl(self) -> None:
        c = self.material.wave_speed()
        r = c * self.geometry.dt / self.geometry.dx
        if r > 1.0:
            new_dt = 0.95 * self.geometry.dx / c
            adjusted = max(1, int(self.geometry.total_time / new_dt))
            self.geometry.n_steps = adjusted
            self._cfl = c * self.geometry.dt / self.geometry.dx
        else:
            self._cfl = r

    def solve(self) -> SimulationResult:
        mat = self.material
        geo = self.geometry
        N = geo.n_nodes
        steps = geo.n_steps
        dx = geo.dx
        dt = geo.dt
        c0 = mat.wave_speed()
        r = self._cfl
        r2 = r * r
        beta = mat.damping

        x = np.linspace(0.0, geo.length, N)
        n_save = steps // geo.save_every + 1
        t_saved = np.zeros(n_save)
        u_save = np.zeros((n_save, N))
        eps_save = np.zeros((n_save, N))
        sig_save = np.zeros((n_save, N))
        dmg_save = np.zeros((n_save, N))
        Eeff_save = np.zeros((n_save, N))

        u_prev = np.zeros(N)
        u_curr = np.zeros(N)
        D = np.zeros(N)
        E_eff = np.full(N, mat.young_modulus)

        top_disp = -geo.load_velocity * dt
        u_curr[0] = top_disp

        save_idx = 0
        self._record(
            save_idx, t_saved, u_save, eps_save, sig_save, dmg_save, Eeff_save,
            0.0, u_curr, D, E_eff, x, dx, mat,
        )
        save_idx += 1

        for n in range(1, steps + 1):
            t = n * dt
            c_local = np.sqrt(E_eff / mat.density)
            r_local = c_local * dt / dx
            r_local = np.clip(r_local, 0.0, 0.98)
            r2_local = r_local * r_local

            u_next = np.zeros(N)
            lap = np.zeros(N)
            lap[1:-1] = u_curr[2:] - 2.0 * u_curr[1:-1] + u_curr[:-2]

            denom = 1.0 + beta * dt
            numer = 2.0 * u_curr - (1.0 - beta * dt) * u_prev + r2_local * lap
            u_next = numer / denom

            u_next[0] = -geo.load_velocity * t
            u_next[-1] = 0.0

            eps = np.zeros(N)
            eps[1:-1] = (u_next[2:] - u_next[:-2]) / (2.0 * dx)
            eps[0] = (u_next[1] - u_next[0]) / dx
            eps[-1] = (u_next[-1] - u_next[-2]) / dx

            sig = E_eff * eps
            sig_eq = np.abs(sig)

            exceeds = sig_eq > mat.critical_stress
            if np.any(exceeds):
                ratio = sig_eq[exceeds] / mat.critical_stress - 1.0
                growth = mat.damage_rate * np.power(ratio, mat.damage_exponent) * dt
                D[exceeds] = np.minimum(
                    D[exceeds] + growth, mat.critical_damage
                )

            E_eff = mat.young_modulus * (
                mat.residual_modulus_ratio
                + (1.0 - mat.residual_modulus_ratio) * (1.0 - D)
            )

            u_prev = u_curr.copy()
            u_curr = u_next.copy()

            if n % geo.save_every == 0 and save_idx < n_save:
                self._record(
                    save_idx, t_saved, u_save, eps_save, sig_save,
                    dmg_save, Eeff_save, t, u_curr, D, E_eff, x, dx, mat,
                )
                save_idx += 1

        actual = save_idx
        return SimulationResult(
            x=x,
            t=t_saved[:actual],
            displacement=u_save[:actual],
            strain=eps_save[:actual],
            stress=sig_save[:actual],
            damage=dmg_save[:actual],
            effective_modulus=Eeff_save[:actual],
            meta={
                "cfl_number": float(self._cfl),
                "wave_speed_m_s": float(c0),
                "dx_mm": float(dx * 1.0e3),
                "dt_us": float(dt * 1.0e6),
                "n_steps": int(steps),
                "n_nodes": int(N),
            },
        )

    @staticmethod
    def _record(
        idx, t_s, u_s, eps_s, sig_s, dmg_s, E_s,
        t, u, D, E_eff, x, dx, mat,
    ) -> None:
        t_s[idx] = t
        u_s[idx] = u
        eps = np.zeros_like(u)
        eps[1:-1] = (u[2:] - u[:-2]) / (2.0 * dx)
        eps[0] = (u[1] - u[0]) / dx
        eps[-1] = (u[-1] - u[-2]) / dx
        eps_s[idx] = eps
        sig_s[idx] = E_eff * eps
        dmg_s[idx] = D
        E_s[idx] = E_eff
