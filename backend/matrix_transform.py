"""
数据矩阵转换路由模块
====================
将求解器输出的原始时空场 (二维 NumPy 数组, 形状 [n_time, n_space]) 转换
/路由为前端不同可视化所需的 JSON 可序列化数据结构。

支持的数据视图 (路由):
    - heatmap       二维应力分布热力图 (t × x 矩阵 + 坐标轴)
    - time_series   某空间点随时间的演化曲线
    - spatial       某时刻沿管轴的空间分布曲线
    - stress_strain 全局/局部应力-应变本构曲线
    - damage_evol   损伤变量统计随时间的演化
    - summary       关键峰值与统计量汇总
"""

from __future__ import annotations

from typing import Any, Dict, List, Tuple

import numpy as np
from scipy.interpolate import RegularGridInterpolator

from solver import SimulationResult

_FIELD_META: Dict[str, Tuple[str, float]] = {
    "stress": ("应力", 1.0e6),
    "strain": ("应变", 1.0),
    "damage": ("损伤", 1.0),
    "displacement": ("位移", 1.0e3),
    "effective_modulus": ("有效模量", 1.0e9),
}


class MatrixTransformer:
    """求解器结果 → 前端可视化数据的转换路由器。"""

    def __init__(self, result: SimulationResult) -> None:
        self.result = result
        self._x_mm = result.x * 1.0e3
        self._t_us = result.t * 1.0e6

    def field_array(self, field: str) -> np.ndarray:
        mapping = {
            "stress": self.result.stress,
            "strain": self.result.strain,
            "damage": self.result.damage,
            "displacement": self.result.displacement,
            "effective_modulus": self.result.effective_modulus,
        }
        if field not in mapping:
            raise ValueError(f"未知物理场: {field}, 可选 {list(mapping)}")
        return mapping[field]

    @staticmethod
    def field_meta(field: str) -> Dict[str, Any]:
        if field not in _FIELD_META:
            raise ValueError(f"未知物理场: {field}")
        label, scale = _FIELD_META[field]
        return {"field": field, "label": label, "scale": scale}

    def to_heatmap(
        self, field: str, target_t: int = 120, target_x: int = 80
    ) -> Dict[str, Any]:
        """将场重采样为目标分辨率的二维矩阵, 供热力图渲染。"""
        arr = self.field_array(field)
        meta = self.field_meta(field)
        scale = meta["scale"]
        data = arr / scale

        nt, nx = data.shape
        tt = target_t if target_t <= nt else nt
        xx = target_x if target_x <= nx else nx

        t_grid = np.linspace(self._t_us[0], self._t_us[-1], nt)
        x_grid = np.linspace(self._x_mm[0], self._x_mm[-1], nx)
        interp = RegularGridInterpolator((t_grid, x_grid), data, method="linear")

        t_new = np.linspace(self._t_us[0], self._t_us[-1], tt)
        x_new = np.linspace(self._x_mm[0], self._x_mm[-1], xx)
        TG, XG = np.meshgrid(t_new, x_new, indexing="ij")
        pts = np.stack([TG.ravel(), XG.ravel()], axis=-1)
        matrix = interp(pts).reshape(tt, xx)

        return {
            "field": field,
            "label": meta["label"],
            "x_axis": np.round(x_new, 4).tolist(),
            "t_axis": np.round(t_new, 3).tolist(),
            "matrix": np.round(matrix, 6).tolist(),
            "vmin": float(np.nanmin(matrix)),
            "vmax": float(np.nanmax(matrix)),
            "n_t": tt,
            "n_x": xx,
        }

    def to_time_series(
        self, field: str, x_fraction: float = 0.5
    ) -> Dict[str, Any]:
        """提取某空间点 (按管长比例) 处场量随时间的演化。"""
        arr = self.field_array(field)
        meta = self.field_meta(field)
        scale = meta["scale"]
        nx = arr.shape[1]
        idx = int(np.clip(x_fraction, 0.0, 1.0) * (nx - 1))
        series = arr[:, idx] / scale
        return {
            "field": field,
            "label": meta["label"],
            "x_position_mm": float(self._x_mm[idx]),
            "t": np.round(self._t_us, 3).tolist(),
            "values": np.round(series, 6).tolist(),
        }

    def to_spatial(
        self, field: str, t_fraction: float = 0.5
    ) -> Dict[str, Any]:
        """提取某时刻 (按总时长比例) 沿管轴的空间分布。"""
        arr = self.field_array(field)
        meta = self.field_meta(field)
        scale = meta["scale"]
        nt = arr.shape[0]
        idx = int(np.clip(t_fraction, 0.0, 1.0) * (nt - 1))
        profile = arr[idx, :] / scale
        return {
            "field": field,
            "label": meta["label"],
            "t_us": float(self._t_us[idx]),
            "x": np.round(self._x_mm, 4).tolist(),
            "values": np.round(profile, 6).tolist(),
        }

    def to_stress_strain(self, x_fraction: float = 0.1) -> Dict[str, Any]:
        """提取某空间点处的应力-应变本构曲线。"""
        stress = self.result.stress
        strain = self.result.strain
        nx = stress.shape[1]
        idx = int(np.clip(x_fraction, 0.0, 1.0) * (nx - 1))
        s = stress[:, idx] / 1.0e6
        e = strain[:, idx]
        order = np.argsort(e)
        return {
            "x_position_mm": float(self._x_mm[idx]),
            "strain": np.round(e[order], 8).tolist(),
            "stress_MPa": np.round(s[order], 4).tolist(),
        }

    def to_damage_evolution(self) -> Dict[str, Any]:
        """损伤统计 (最大值/平均值/失效比例) 随时间演化。"""
        D = self.result.damage
        max_d = np.max(D, axis=1)
        mean_d = np.mean(D, axis=1)
        failed_frac = np.mean(D >= 0.85, axis=1)
        return {
            "t": np.round(self._t_us, 3).tolist(),
            "max_damage": np.round(max_d, 5).tolist(),
            "mean_damage": np.round(mean_d, 5).tolist(),
            "failed_fraction": np.round(failed_frac, 5).tolist(),
        }

    def to_summary(self) -> Dict[str, Any]:
        """关键峰值与统计量汇总。"""
        s = self.result.summary()
        s.update(self.result.meta)
        s["total_length_mm"] = float(self.result.x[-1] * 1.0e3)
        s["total_time_us"] = float(self.result.t[-1] * 1.0e6)
        return s

    def to_animation_frames(
        self, field: str, n_frames: int = 24
    ) -> List[Dict[str, Any]]:
        """为动画播放抽取若干关键帧的空间分布。"""
        arr = self.field_array(field)
        meta = self.field_meta(field)
        scale = meta["scale"]
        nt = arr.shape[0]
        indices = np.linspace(0, nt - 1, n_frames, dtype=int)
        frames: List[Dict[str, Any]] = []
        for fi in indices:
            frames.append(
                {
                    "t_us": float(self._t_us[fi]),
                    "x": np.round(self._x_mm, 4).tolist(),
                    "values": np.round(arr[fi, :] / scale, 6).tolist(),
                }
            )
        return frames


def route(result: SimulationResult, view: str, **kwargs) -> Dict[str, Any]:
    """统一路由入口: 依据 view 名称分发到对应转换方法。"""
    tf = MatrixTransformer(result)
    routing = {
        "heatmap": lambda: tf.to_heatmap(
            kwargs.get("field", "stress"),
            kwargs.get("target_t", 120),
            kwargs.get("target_x", 80),
        ),
        "time_series": lambda: tf.to_time_series(
            kwargs.get("field", "stress"),
            kwargs.get("x_fraction", 0.5),
        ),
        "spatial": lambda: tf.to_spatial(
            kwargs.get("field", "stress"),
            kwargs.get("t_fraction", 0.5),
        ),
        "stress_strain": lambda: tf.to_stress_strain(
            kwargs.get("x_fraction", 0.1),
        ),
        "damage_evolution": tf.to_damage_evolution,
        "summary": tf.to_summary,
        "animation": lambda: tf.to_animation_frames(
            kwargs.get("field", "stress"),
            kwargs.get("n_frames", 24),
        ),
    }
    if view not in routing:
        raise ValueError(f"未知视图: {view}, 可选 {list(routing)}")
    return routing[view]()
