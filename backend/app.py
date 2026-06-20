"""
Flask API 服务模块
==================
桥接 Python 求解器与 React 前端, 提供 REST 接口:

    GET  /api/health              健康检查
    GET  /api/params              默认参数与字段元数据 (供配置面板)
    POST /api/simulate            提交参数运行求解, 返回汇总
    GET  /api/view/<view>         获取指定视图的转换数据
    GET  /api/views               一次性获取全部视图
    POST /api/simulate_full       一步完成: 求解 + 返回全部视图
"""

from __future__ import annotations

import math
import time
from typing import Any, Dict

from flask import Flask, jsonify, request
from flask_cors import CORS

from solver import (
    BambooFiberSolver,
    GeometryParams,
    MaterialParams,
    SimulationResult,
)
from matrix_transform import MatrixTransformer, route

app = Flask(__name__)
CORS(app)

_cache: Dict[str, Any] = {"result": None, "params": None, "timestamp": 0.0}

PARAM_SCHEMA: Dict[str, Any] = {
    "material": {
        "young_modulus": {"unit": "GPa", "min": 1.0, "max": 80.0, "step": 0.5,
                          "default": 18.0, "label": "杨氏模量 E"},
        "density": {"unit": "kg/m³", "min": 300.0, "max": 2000.0, "step": 10.0,
                    "default": 850.0, "label": "密度 ρ"},
        "damping": {"unit": "1/s", "min": 0.0, "max": 5.0e4, "step": 100.0,
                    "default": 0.0, "label": "瑞利阻尼 β"},
        "critical_stress": {"unit": "MPa", "min": 5.0, "max": 200.0, "step": 1.0,
                             "default": 25.0, "label": "损伤起始应力 σ_c0"},
        "damage_rate": {"unit": "1/s", "min": 0.0, "max": 5.0e4, "step": 100.0,
                        "default": 8000.0, "label": "损伤速率系数 A"},
        "damage_exponent": {"unit": "-", "min": 0.5, "max": 4.0, "step": 0.1,
                            "default": 1.5, "label": "损伤指数 m"},
        "critical_damage": {"unit": "-", "min": 0.3, "max": 0.99, "step": 0.01,
                             "default": 0.85, "label": "临界损伤 D_c"},
        "residual_modulus_ratio": {"unit": "-", "min": 0.0, "max": 0.5, "step": 0.01,
                                    "default": 0.05, "label": "残余模量比"},
    },
    "geometry": {
        "length": {"unit": "m", "min": 0.05, "max": 2.0, "step": 0.05,
                   "default": 0.5, "label": "管壁长度 L"},
        "n_nodes": {"unit": "-", "min": 51, "max": 801, "step": 10,
                    "default": 201, "label": "空间节点数"},
        "load_velocity": {"unit": "m/s", "min": 0.5, "max": 50.0, "step": 0.5,
                          "default": 12.0, "label": "加载速度 v₀"},
        "total_time": {"unit": "μs", "min": 50.0, "max": 2000.0, "step": 10.0,
                       "default": 400.0, "label": "总仿真时长"},
        "n_steps": {"unit": "-", "min": 1000, "max": 40000, "step": 500,
                   "default": 8000, "label": "时间步数"},
        "save_every": {"unit": "-", "min": 1, "max": 50, "step": 1,
                       "default": 16, "label": "存帧间隔"},
    },
}


def build_params(payload: Dict[str, Any]):
    mat_def = MaterialParams()
    geo_def = GeometryParams()
    mp = payload.get("material", {})
    gp = payload.get("geometry", {})

    material = MaterialParams(
        young_modulus=mp.get("young_modulus", mat_def.young_modulus / 1e9) * 1e9,
        density=mp.get("density", mat_def.density),
        damping=mp.get("damping", mat_def.damping),
        critical_stress=mp.get("critical_stress", mat_def.critical_stress / 1e6) * 1e6,
        damage_rate=mp.get("damage_rate", mat_def.damage_rate),
        damage_exponent=mp.get("damage_exponent", mat_def.damage_exponent),
        critical_damage=mp.get("critical_damage", mat_def.critical_damage),
        residual_modulus_ratio=mp.get("residual_modulus_ratio", mat_def.residual_modulus_ratio),
    )
    geometry = GeometryParams(
        length=gp.get("length", geo_def.length),
        n_nodes=int(gp.get("n_nodes", geo_def.n_nodes)),
        load_velocity=gp.get("load_velocity", geo_def.load_velocity),
        total_time=gp.get("total_time", geo_def.total_time * 1e6) * 1e-6,
        n_steps=int(gp.get("n_steps", geo_def.n_steps)),
        save_every=int(gp.get("save_every", geo_def.save_every)),
    )
    return material, geometry


def run_simulation(payload: Dict[str, Any]) -> Dict[str, Any]:
    material, geometry = build_params(payload)
    t0 = time.time()
    solver = BambooFiberSolver(material, geometry)
    result = solver.solve()
    elapsed = time.time() - t0

    _cache["result"] = result
    _cache["params"] = payload
    _cache["timestamp"] = time.time()

    summary = MatrixTransformer(result).to_summary()
    summary["compute_time_s"] = round(elapsed, 3)
    summary["cfl_number"] = round(summary.get("cfl_number", 0.0), 4)
    return summary


@app.route("/api/health")
def health():
    return jsonify({"status": "ok", "service": "bamboo-fiber-solver"})


@app.route("/api/params")
def get_params():
    defaults = {
        "material": {k: v["default"] for k, v in PARAM_SCHEMA["material"].items()},
        "geometry": {k: v["default"] for k, v in PARAM_SCHEMA["geometry"].items()},
    }
    return jsonify({"schema": PARAM_SCHEMA, "defaults": defaults})


@app.route("/api/simulate", methods=["POST"])
def simulate():
    payload = request.get_json(force=True) or {}
    try:
        summary = run_simulation(payload)
    except Exception as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(summary)


@app.route("/api/view/<view>")
def get_view(view):
    result: SimulationResult | None = _cache.get("result")
    if result is None:
        return jsonify({"error": "尚未运行仿真, 请先 POST /api/simulate"}), 404
    args = {k: v for k, v in request.args.items()}
    for key in ("x_fraction", "t_fraction"):
        if key in args:
            args[key] = float(args[key])
    for key in ("target_t", "target_x", "n_frames"):
        if key in args:
            args[key] = int(args[key])
    try:
        data = route(result, view, **args)
    except Exception as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(data)


@app.route("/api/views")
def get_all_views():
    result: SimulationResult | None = _cache.get("result")
    if result is None:
        return jsonify({"error": "尚未运行仿真, 请先 POST /api/simulate"}), 404
    tf = MatrixTransformer(result)
    return jsonify({
        "summary": tf.to_summary(),
        "heatmap_stress": tf.to_heatmap("stress"),
        "heatmap_damage": tf.to_heatmap("damage", 120, 80),
        "time_series_stress": tf.to_time_series("stress", 0.5),
        "time_series_damage": tf.to_time_series("damage", 0.5),
        "spatial_stress": tf.to_spatial("stress", 0.6),
        "spatial_damage": tf.to_spatial("damage", 0.9),
        "stress_strain": tf.to_stress_strain(0.1),
        "damage_evolution": tf.to_damage_evolution(),
        "animation": tf.to_animation_frames("stress", 20),
    })


@app.route("/api/simulate_full", methods=["POST"])
def simulate_full():
    payload = request.get_json(force=True) or {}
    try:
        summary = run_simulation(payload)
    except Exception as exc:
        return jsonify({"error": str(exc)}), 400
    result = _cache["result"]
    tf = MatrixTransformer(result)
    return jsonify({
        "summary": summary,
        "heatmap_stress": tf.to_heatmap("stress"),
        "heatmap_damage": tf.to_heatmap("damage", 120, 80),
        "time_series_stress": tf.to_time_series("stress", 0.5),
        "time_series_damage": tf.to_time_series("damage", 0.5),
        "spatial_stress": tf.to_spatial("stress", 0.6),
        "spatial_damage": tf.to_spatial("damage", 0.9),
        "stress_strain": tf.to_stress_strain(0.1),
        "damage_evolution": tf.to_damage_evolution(),
        "animation": tf.to_animation_frames("stress", 20),
    })


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5001, debug=True)
