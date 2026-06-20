"""
Flask API 服务模块
==================
桥接 Python 求解器与 React 前端, 提供 REST 接口:

同步接口 (适用于瞬态波动/短时长仿真, < 1 分钟):
    GET  /api/health              健康检查
    GET  /api/params              默认参数与字段元数据
    POST /api/simulate            同步求解并返回汇总
    POST /api/simulate_full       同步: 求解 + 返回全部视图
    GET  /api/view/<view>         获取指定视图
    GET  /api/views               一次性获取全部视图

异步接口 (适用于长时 24h 准静态仿真, 避免 504 超时):
    POST /api/simulate_async      提交异步任务, 立即返回 task_id
    GET  /api/task/<task_id>      查询任务进度/状态
    GET  /api/tasks               全部任务列表
    POST /api/task/<id>/cancel    取消进行中的任务

两种仿真模式:
  1. wave         = 瞬态波动 FDM (原 BambooFiberSolver)
  2. quasi_static = 长时准静态蠕变损伤 (QuasiStaticDamageSolver)
"""

from __future__ import annotations

import secrets
import threading
import time
import traceback
from dataclasses import dataclass, field
from typing import Any, Dict, Optional

from flask import Flask, jsonify, request
from flask_cors import CORS

from solver import (
    BambooFiberSolver,
    GeometryParams,
    MaterialParams,
    QuasiStaticDamageSolver,
    SimulationResult,
    create_solver,
)
from matrix_transform import MatrixTransformer, route

app = Flask(__name__)
CORS(app)

_cache: Dict[str, Any] = {"result": None, "params": None, "timestamp": 0.0}

TASKS: Dict[str, "AsyncTask"] = {}
_TASKS_LOCK = threading.Lock()


@dataclass
class AsyncTask:
    task_id: str
    status: str = "queued"
    progress_pct: int = 0
    message: str = "任务已提交，等待执行"
    payload: Dict[str, Any] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)
    started_at: Optional[float] = None
    finished_at: Optional[float] = None
    compute_time_s: Optional[float] = None
    summary: Optional[Dict[str, Any]] = None
    views: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    live_stats: Dict[str, Any] = field(default_factory=dict)
    _cancel_flag: bool = False
    _thread: Optional[threading.Thread] = None


PARAM_SCHEMA: Dict[str, Any] = {
    "mode": {
        "sim_mode": {
            "type": "select",
            "options": [
                {"value": "wave", "label": "瞬态波动模式 (冲击加载, μs~ms)"},
                {"value": "quasi_static", "label": "长时准静态模式 (持续受压, 小时级)"},
            ],
            "default": "wave",
            "label": "仿真模式",
        },
        "damage_model": {
            "type": "select",
            "options": [
                {"value": "power", "label": "幂律损伤模型 (应力阈值型)"},
                {"value": "creep", "label": "蠕变损伤模型 (Kachanov-Rabotnov)"},
            ],
            "default": "power",
            "label": "损伤演化模型",
        },
        "use_async": {
            "type": "boolean",
            "default": False,
            "label": "使用异步任务模式 (避免 504 超时)",
        },
    },
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
        "creep_B": {"unit": "1/s·MPa^-α", "min": 1.0e-20, "max": 1.0e-5, "step": 1.0e-12,
                    "default": 8.0e-10, "label": "蠕变系数 B (log scale)", "mode": "creep"},
        "creep_alpha": {"unit": "-", "min": 1.0, "max": 8.0, "step": 0.1,
                        "default": 3.5, "label": "蠕变应力指数 α", "mode": "creep"},
        "creep_chi": {"unit": "-", "min": 0.1, "max": 5.0, "step": 0.1,
                      "default": 1.5, "label": "蠕变损伤指数 χ", "mode": "creep"},
    },
    "geometry": {
        "length": {"unit": "m", "min": 0.05, "max": 2.0, "step": 0.05,
                   "default": 0.5, "label": "管壁长度 L"},
        "n_nodes": {"unit": "-", "min": 51, "max": 801, "step": 10,
                    "default": 201, "label": "空间节点数"},
        "load_velocity_wave": {"unit": "m/s", "min": 0.5, "max": 50.0, "step": 0.5,
                               "default": 12.0, "label": "冲击加载速度 v₀", "mode": "wave"},
        "load_velocity_qs": {"unit": "1/s (应变率)", "min": 1.0e-10, "max": 1.0e-5, "step": 1.0e-9,
                             "default": 8.0e-8, "label": "蠕变应变率 ε̇", "mode": "quasi_static"},
        "total_time_wave": {"unit": "μs", "min": 50.0, "max": 5000.0, "step": 50.0,
                            "default": 400.0, "label": "总仿真时长", "mode": "wave"},
        "total_time_qs": {"unit": "h", "min": 0.5, "max": 720.0, "step": 0.5,
                          "default": 24.0, "label": "总仿真时长", "mode": "quasi_static"},
        "n_steps": {"unit": "-", "min": 1000, "max": 40000, "step": 500,
                   "default": 8000, "label": "时间步数", "mode": "wave"},
        "save_every": {"unit": "-", "min": 1, "max": 200, "step": 1,
                       "default": 16, "label": "存帧间隔"},
    },
}


def _defaults_from_schema(schema_group):
    return {k: v["default"] for k, v in schema_group.items()}


def get_sim_mode(payload: Dict[str, Any]) -> str:
    return (payload.get("mode", {}) or {}).get("sim_mode", "wave").strip().lower()


def build_material(payload: Dict[str, Any]) -> MaterialParams:
    mp = payload.get("material", {}) or {}
    mat_def = MaterialParams()
    return MaterialParams(
        young_modulus=mp.get("young_modulus", mat_def.young_modulus / 1e9) * 1e9,
        density=mp.get("density", mat_def.density),
        damping=mp.get("damping", mat_def.damping),
        critical_stress=mp.get("critical_stress", mat_def.critical_stress / 1e6) * 1e6,
        damage_rate=mp.get("damage_rate", mat_def.damage_rate),
        damage_exponent=mp.get("damage_exponent", mat_def.damage_exponent),
        critical_damage=mp.get("critical_damage", mat_def.critical_damage),
        residual_modulus_ratio=mp.get("residual_modulus_ratio", mat_def.residual_modulus_ratio),
        creep_B=mp.get("creep_B", mat_def.creep_B),
        creep_alpha=mp.get("creep_alpha", mat_def.creep_alpha),
        creep_chi=mp.get("creep_chi", mat_def.creep_chi),
        damage_model=(payload.get("mode", {}) or {}).get("damage_model", mat_def.damage_model),
    )


def build_geometry(payload: Dict[str, Any]) -> GeometryParams:
    gp = payload.get("geometry", {}) or {}
    mode = get_sim_mode(payload)
    geo_def = GeometryParams()

    if mode == "quasi_static":
        load_velocity = gp.get("load_velocity_qs", 8e-8)
        total_time_h = gp.get("total_time_qs", 24.0)
        total_time_s = total_time_h * 3600.0
        n_steps = int(max(500, min(10000, int(total_time_s / 100))))
        return GeometryParams(
            length=gp.get("length", geo_def.length),
            n_nodes=int(gp.get("n_nodes", geo_def.n_nodes)),
            load_velocity=float(load_velocity),
            total_time=float(total_time_s),
            n_steps=n_steps,
            save_every=int(gp.get("save_every", geo_def.save_every)),
        )
    else:
        return GeometryParams(
            length=gp.get("length", geo_def.length),
            n_nodes=int(gp.get("n_nodes", geo_def.n_nodes)),
            load_velocity=float(gp.get("load_velocity_wave", geo_def.load_velocity)),
            total_time=float(gp.get("total_time_wave", geo_def.total_time * 1e6) * 1e-6),
            n_steps=int(gp.get("n_steps", geo_def.n_steps)),
            save_every=int(gp.get("save_every", geo_def.save_every)),
        )


def build_result_views(result: SimulationResult) -> Dict[str, Any]:
    tf = MatrixTransformer(result)
    return {
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
    }


def _execute_solve(
    payload: Dict[str, Any],
    progress_cb=None,
    cancel_flag=None,
) -> Dict[str, Any]:
    mode = get_sim_mode(payload)
    material = build_material(payload)
    geometry = build_geometry(payload)
    t0 = time.time()
    solver = create_solver(mode, material, geometry)

    kwargs = {}
    if mode == "quasi_static" and hasattr(solver, "solve"):
        if progress_cb is not None:
            kwargs["progress_cb"] = progress_cb
        if cancel_flag is not None:
            kwargs["cancel_flag"] = cancel_flag

    result = solver.solve(**kwargs)
    elapsed = time.time() - t0

    _cache["result"] = result
    _cache["params"] = payload
    _cache["timestamp"] = time.time()

    summary = MatrixTransformer(result).to_summary()
    summary["compute_time_s"] = round(elapsed, 3)
    summary["cfl_number"] = round(summary.get("cfl_number", 0.0), 4)
    summary["sim_mode"] = mode
    summary["meta"] = result.meta
    return summary


# =====================================================================
# 异步任务管理
# =====================================================================

def _create_task(payload: Dict[str, Any]) -> AsyncTask:
    task_id = "t_" + secrets.token_hex(6)
    task = AsyncTask(task_id=task_id, payload=payload)
    with _TASKS_LOCK:
        TASKS[task_id] = task
    return task


def _progress_maker(task: AsyncTask):
    def cb(step: int, est: int, info: Dict[str, Any]):
        task.progress_pct = int(info.get("progress_pct", 0))
        task.live_stats = info.copy()
        pct = task.progress_pct
        parts = []
        if "t_hours" in info:
            parts.append(f"已推进 {info['t_hours']:.1f}h")
        if "max_damage" in info:
            parts.append(f"D_max={info['max_damage']:.4f}")
        if "max_stress_MPa" in info:
            parts.append(f"σ_max={info['max_stress_MPa']:.1f}MPa")
        if info.get("done"):
            task.message = "求解完成，正在转换结果视图…"
        else:
            task.message = f"进度 {pct}%  " + "  ·  ".join(parts)
    return cb


def _run_task(task: AsyncTask) -> None:
    task.status = "running"
    task.started_at = time.time()
    try:
        cancel = lambda: task._cancel_flag
        progress_cb = _progress_maker(task)
        summary = _execute_solve(task.payload, progress_cb=progress_cb, cancel_flag=cancel)
        if task._cancel_flag:
            task.status = "cancelled"
            task.message = "任务已取消"
            task.progress_pct = 0
        else:
            task.progress_pct = 95
            task.message = "求解完成，正在生成可视化视图…"
            result = _cache.get("result")
            if result is not None:
                task.views = build_result_views(result)
                task.summary = task.views["summary"]
                task.summary["compute_time_s"] = summary.get("compute_time_s")
                task.summary["sim_mode"] = summary.get("sim_mode")
            task.status = "done"
            task.message = "任务完成"
            task.progress_pct = 100
    except Exception as exc:
        task.status = "error"
        task.message = f"求解失败: {exc}"
        task.error = traceback.format_exc()
    finally:
        task.finished_at = time.time()
        if task.summary and task.summary.get("compute_time_s") is None:
            task.summary = task.summary or {}
            task.summary["compute_time_s"] = round((task.finished_at - task.started_at), 3)


def submit_async_task(payload: Dict[str, Any]) -> AsyncTask:
    task = _create_task(payload)
    thread = threading.Thread(target=_run_task, args=(task,), daemon=True)
    task._thread = thread
    thread.start()
    return task


def task_to_dict(task: AsyncTask, include_views: bool = False) -> Dict[str, Any]:
    out = {
        "task_id": task.task_id,
        "status": task.status,
        "progress_pct": task.progress_pct,
        "message": task.message,
        "created_at": round(task.created_at, 3),
        "started_at": round(task.started_at, 3) if task.started_at else None,
        "finished_at": round(task.finished_at, 3) if task.finished_at else None,
        "compute_time_s": (
            round(task.finished_at - task.started_at, 3)
            if task.finished_at and task.started_at else None
        ),
        "live_stats": task.live_stats,
        "error": task.error,
        "summary": task.summary,
    }
    if include_views and task.views is not None:
        out["views"] = task.views
    return out


# =====================================================================
# Flask 路由
# =====================================================================

@app.route("/api/health")
def health():
    return jsonify({
        "status": "ok",
        "service": "bamboo-fiber-solver",
        "queued_tasks": sum(1 for t in TASKS.values() if t.status == "queued"),
        "running_tasks": sum(1 for t in TASKS.values() if t.status == "running"),
    })


@app.route("/api/params")
def get_params():
    defaults = {
        "mode": _defaults_from_schema(PARAM_SCHEMA["mode"]),
        "material": _defaults_from_schema(PARAM_SCHEMA["material"]),
        "geometry": _defaults_from_schema(PARAM_SCHEMA["geometry"]),
    }
    return jsonify({"schema": PARAM_SCHEMA, "defaults": defaults})


@app.route("/api/simulate", methods=["POST"])
def simulate():
    payload = request.get_json(force=True) or {}
    try:
        summary = _execute_solve(payload)
    except Exception as exc:
        return jsonify({"error": str(exc), "traceback": traceback.format_exc()}), 400
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
    return jsonify(build_result_views(result))


@app.route("/api/simulate_full", methods=["POST"])
def simulate_full():
    payload = request.get_json(force=True) or {}
    try:
        summary = _execute_solve(payload)
    except Exception as exc:
        return jsonify({"error": str(exc), "traceback": traceback.format_exc()}), 400
    views = build_result_views(_cache["result"])
    views["summary"] = summary
    return jsonify(views)


# -------------------------------------------------------------------
# 新增异步接口
# -------------------------------------------------------------------

@app.route("/api/simulate_async", methods=["POST"])
def simulate_async():
    payload = request.get_json(force=True) or {}
    try:
        task = submit_async_task(payload)
    except Exception as exc:
        return jsonify({"error": str(exc), "traceback": traceback.format_exc()}), 400
    return jsonify(task_to_dict(task))


@app.route("/api/task/<task_id>")
def get_task(task_id):
    task = TASKS.get(task_id)
    if task is None:
        return jsonify({"error": f"task_id {task_id} 不存在"}), 404
    include_views = request.args.get("include_views", "1") not in ("0", "false", "False")
    return jsonify(task_to_dict(task, include_views=include_views))


@app.route("/api/tasks")
def list_tasks():
    items = sorted(TASKS.values(), key=lambda t: t.created_at, reverse=True)[:50]
    return jsonify({"tasks": [task_to_dict(t) for t in items]})


@app.route("/api/task/<task_id>/cancel", methods=["POST"])
def cancel_task(task_id):
    task = TASKS.get(task_id)
    if task is None:
        return jsonify({"error": f"task_id {task_id} 不存在"}), 404
    if task.status in ("running", "queued"):
        task._cancel_flag = True
        if task.status == "queued":
            task.status = "cancelled"
            task.message = "任务已取消"
    return jsonify(task_to_dict(task))


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5001, debug=True, threaded=True)
