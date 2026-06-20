"""
应力公式求解器模块
====================
求解竹纤维复合材料管壁在轴向受压状态下的一维波动方程与局部损伤演化。

提供两种求解模式:

[A] 瞬态波动模式 (BambooFiberSolver)
    适用场景: 冲击加载 / 应力波传播 (微秒 ~ 毫秒级)
    控制方程: ∂²u/∂t² + 2β ∂u/∂t = c² ∂²u/∂x²  (显式中心差分 FDM)

[B] 长时准静态模式 (QuasiStaticDamageSolver)
    适用场景: 持续受压 / 全天 24h 微小损伤累积 (小时级)
    控制方程: 弹性准静态平衡 + 蠕变/幂律损伤演化
              跳过高频弹性波, 时间步长由损伤演化稳定性决定

应变: ε(x, t) = ∂u/∂x
应力: σ(x, t) = E_eff(x, t) · ε(x, t)
有效模量: E_eff = E · (1 - D), D ∈ [0, 1] 为损伤变量

损伤演化 (两种):
    幂律模型 (应力阈值型):
        dD/dt = A · (σ_eq / σ_c0 - 1)^m,  σ_eq > σ_c0
    蠕变模型 (Kachanov-Rabotnov 型):
        dD/dt = B · σ_eq^α · (1 - D)^(-χ)
    D 上限为临界损伤 D_c, 超过即视为局部破坏。
"""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Tuple

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
    creep_B: float = 1.2e-26
    creep_alpha: float = 4.0
    creep_chi: float = 2.0
    damage_model: str = "power"

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


ProgressCallback = Optional[Callable[[int, int, Dict], None]]


class QuasiStaticDamageSolver:
    """竹纤维复合材料长时准静态损伤演化求解器。

    物理近似:
        - 弹性惯性项可忽略, 每一步直接达到准静态平衡
        - 一维受压杆: 若损伤沿空间不均匀, 则内力处处相等, 即
              σ(x) · A(x) = N(t)  (轴力均匀)
          此处 A ∝ E_eff(x) = E·(1-D(x)), 故
              ε(x) = N(t) / E_eff(x) = 平均应力 / (1 - k - (1-k)(1-D))
        - 位移由积分应变得到, 并满足边界条件 u(L) = 0

    时间步长由损伤演化的显式稳定性决定:
        要求单步损伤增长 ΔD << (1 - D), 通常取 Δt 使得最大 ΔD ≈ 0.01
    """

    def __init__(
        self,
        material: MaterialParams | None = None,
        geometry: GeometryParams | None = None,
    ) -> None:
        self.material = material or MaterialParams()
        self.geometry = geometry or GeometryParams()

    def _damage_rate(self, sigma_eq: np.ndarray, D: np.ndarray) -> np.ndarray:
        """计算损伤率 dD/dt (基于所选本构模型)。"""
        mat = self.material
        if mat.damage_model == "creep":
            B, alpha, chi = mat.creep_B, mat.creep_alpha, mat.creep_chi
            sig_ref = 1.0e6
            dDdt = B * np.power(sigma_eq / sig_ref, alpha)
            denom = np.power(np.maximum(1.0 - D, 1e-3), chi)
            return dDdt / denom
        else:
            A, m, sigma_c = mat.damage_rate, mat.damage_exponent, mat.critical_stress
            dDdt = np.zeros_like(sigma_eq)
            mask = sigma_eq > sigma_c
            ratio = sigma_eq[mask] / sigma_c - 1.0
            dDdt[mask] = A * np.power(ratio, m)
            return dDdt

    def _auto_timestep(self, sigma_eq: np.ndarray, D: np.ndarray) -> float:
        """依据损伤率自动选取稳定的时间步长。"""
        T = self.geometry.total_time
        dDdt = self._damage_rate(sigma_eq, D)
        dDdt_max = float(np.max(dDdt))
        target_delta = 0.005
        if dDdt_max > 0.0:
            dt_safe = target_delta / dDdt_max
        else:
            dt_safe = T / 100.0
        dt_min = max(T / 10000.0, 1.0)
        dt_max = max(T / 100.0, 60.0)
        return float(np.clip(dt_safe, dt_min, dt_max))

    def _quasi_static_equilibrium(
        self, D: np.ndarray, applied_strain: float,
    ) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """
        一维受压杆准静态平衡求解。

        边界: u(x=0) 加载端, u(x=L)=0 固定端。
        平衡条件: dσ/dx = 0, 即 σ = 常数 (不计体力)。

        给定名义应变 ε_nominal = applied_strain = Δ/L (Δ为总压缩量),
        当损伤空间不均匀时, 实际应变 ε(x) 会重分配以满足 σ 守恒:
          - 设 σ 为未知常数
          - ε(x) = σ / E_eff(x)
          - ∫₀ᴸ ε(x) dx = Δ = applied_strain * L
          - 由 σ * ∫₀ᴸ 1/E_eff(x) dx = applied_strain * L
          - 故 σ = applied_strain * L / ∫₀ᴸ (1/E_eff) dx
        """
        mat = self.material
        geo = self.geometry
        N_nodes = len(D)
        dx = geo.dx
        L = geo.length

        E_eff = mat.young_modulus * (
            mat.residual_modulus_ratio
            + (1.0 - mat.residual_modulus_ratio) * (1.0 - D)
        )
        inv_E = 1.0 / np.maximum(E_eff, 1e6)
        integral_inv_E = 0.5 * dx * (inv_E[0] + inv_E[-1]) + dx * np.sum(inv_E[1:-1])
        sigma_value = (applied_strain * L) / max(integral_inv_E, 1e-20)
        eps = sigma_value * inv_E

        u = np.zeros(N_nodes)
        cum = 0.0
        u[0] = -applied_strain * L
        for i in range(1, N_nodes):
            cum += 0.5 * (eps[i] + eps[i - 1]) * dx
            u[i] = u[0] + cum
        eps[0] = (u[1] - u[0]) / dx
        eps[-1] = (u[-1] - u[-2]) / dx
        sigma = E_eff * eps
        return u, eps, sigma

    def solve(
        self,
        progress_cb: ProgressCallback = None,
        cancel_flag: Optional[Callable[[], bool]] = None,
    ) -> SimulationResult:
        mat = self.material
        geo = self.geometry
        N = geo.n_nodes
        T = geo.total_time
        save_every = max(1, geo.save_every)
        n_save_target = 500
        save_interval_max = T / n_save_target

        x = np.linspace(0.0, geo.length, N)
        strain_rate_per_sec = geo.load_velocity
        eps_ramp_time = max(T * 0.05, 1.0 / max(strain_rate_per_sec, 1e-15), 60.0)
        eps_ramp_time = min(eps_ramp_time, T * 0.2)
        eps_applied_total = strain_rate_per_sec * eps_ramp_time
        eps_applied_total = max(eps_applied_total, 1.0e-4)

        rng = np.random.default_rng(42)
        fiber_perturb = rng.normal(0.0, 0.015, N)
        fiber_perturb = np.clip(fiber_perturb, -0.05, 0.05)
        D = fiber_perturb
        D[D < 0.0] = 0.0
        D = D * 0.02
        t = 0.0
        step = 0
        t_saved = [0.0]
        u_save_list: List[np.ndarray] = []
        eps_save_list: List[np.ndarray] = []
        sig_save_list: List[np.ndarray] = []
        dmg_save_list: List[np.ndarray] = []
        Eeff_save_list: List[np.ndarray] = []

        E_eff_0 = mat.young_modulus * (
            mat.residual_modulus_ratio
            + (1.0 - mat.residual_modulus_ratio) * (1.0 - D)
        )
        eps_0_init = eps_applied_total * 0.01
        u_0, eps_0, sig_0 = self._quasi_static_equilibrium(D, eps_0_init)

        u_save_list.append(u_0)
        eps_save_list.append(eps_0)
        sig_save_list.append(sig_0)
        dmg_save_list.append(D.copy())
        Eeff_save_list.append(E_eff_0.copy())

        next_save_t = save_interval_max
        progress_est = 0
        est_total_steps_ub = 5000

        while t < T:
            if cancel_flag and cancel_flag():
                break

            if t < eps_ramp_time:
                eps_target = eps_applied_total * (t / eps_ramp_time)
            else:
                eps_target = eps_applied_total
            eps_target = max(eps_target, eps_applied_total * 0.01)

            u, eps, sigma = self._quasi_static_equilibrium(D, eps_target)
            sigma_eq = np.abs(sigma)

            dDdt = self._damage_rate(sigma_eq, D)
            dt_auto = self._auto_timestep(sigma_eq, D)
            dt = min(dt_auto, T - t, save_interval_max * 0.5)
            dt = max(dt, 1.0e-6)

            growth = dDdt * dt
            D = np.minimum(D + growth, mat.critical_damage)

            t += dt
            step += 1

            if t >= next_save_t or step % save_every == 0 or t >= T:
                E_eff = mat.young_modulus * (
                    mat.residual_modulus_ratio
                    + (1.0 - mat.residual_modulus_ratio) * (1.0 - D)
                )
                u_f, eps_f, sigma_f = self._quasi_static_equilibrium(D, eps_target)
                t_saved.append(t)
                u_save_list.append(u_f)
                eps_save_list.append(eps_f)
                sig_save_list.append(sigma_f)
                dmg_save_list.append(D.copy())
                Eeff_save_list.append(E_eff.copy())
                next_save_t = t + save_interval_max

            if progress_cb and step % 10 == 0:
                progress_est = min(99, int(100 * t / T))
                progress_cb(step, est_total_steps_ub, {
                    "t_hours": t / 3600.0,
                    "max_damage": float(np.max(D)),
                    "max_stress_MPa": float(np.max(sigma_eq) / 1.0e6),
                    "progress_pct": progress_est,
                    "dt_seconds": float(dt),
                })

        t_arr = np.array(t_saved)
        out = SimulationResult(
            x=x,
            t=t_arr,
            displacement=np.array(u_save_list),
            strain=np.array(eps_save_list),
            stress=np.array(sig_save_list),
            damage=np.array(dmg_save_list),
            effective_modulus=np.array(Eeff_save_list),
            meta={
                "mode": "quasi_static",
                "total_time_hours": float(T / 3600.0),
                "n_steps": int(step),
                "n_nodes": int(N),
                "dx_mm": float(geo.dx * 1.0e3),
                "mean_dt_seconds": float(T / max(1, step)),
                "wave_speed_m_s": float(mat.wave_speed()),
            },
        )
        if progress_cb:
            progress_cb(step, step, {
                "t_hours": T / 3600.0,
                "max_damage": float(np.max(D)),
                "max_stress_MPa": float(np.max(np.abs(out.stress)) / 1.0e6),
                "progress_pct": 100,
                "done": True,
            })
        return out


def create_solver(
    mode: str,
    material: MaterialParams | None = None,
    geometry: GeometryParams | None = None,
):
    """工厂方法: 依据模式字符串返回对应求解器实例。

    mode ∈ {"wave", "quasi_static"}
    """
    mode = (mode or "wave").strip().lower()
    if mode == "quasi_static" or mode == "longterm" or mode == "long_term":
        return QuasiStaticDamageSolver(material, geometry)
    return BambooFiberSolver(material, geometry)
