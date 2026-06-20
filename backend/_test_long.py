import time
from solver import MaterialParams, GeometryParams, create_solver

mat = MaterialParams(
    young_modulus=18e9,
    density=850,
    critical_stress=15e6,
    damage_model='creep',
    creep_B=8e-10,
    creep_alpha=3.5,
    creep_chi=1.5,
)
geo = GeometryParams(
    length=0.5,
    n_nodes=201,
    load_velocity=8e-8,          # 应变率, 最终应变 ≈ 0.15%
    total_time=24 * 3600,
    save_every=50,
)
t0 = time.time()
solver = create_solver('quasi_static', mat, geo)

prog_lines = []
def progress(step, est, info):
    if step % 500 == 0 or info.get('done'):
        prog_lines.append(
            f"  step={step:4d} pct={info.get('progress_pct',0):3d}%"
            f" Dmax={info.get('max_damage',0):.5f} t={info.get('t_hours',0):.1f}h"
            f" σmax={info.get('max_stress_MPa',0):.2f}MPa"
            f" dt={info.get('dt_seconds',0):.0f}s"
        )

res = solver.solve(progress_cb=progress)
elapsed = time.time() - t0
for l in prog_lines:
    print(l)
print(f"\n总耗时 {elapsed:.2f}s, 时间步数={res.meta['n_steps']}, 存帧数={res.stress.shape[0]}")
print('应力范围 (MPa):', round(res.stress.min()/1e6, 3), '~', round(res.stress.max()/1e6, 3))
print('损伤范围:', round(res.damage.min(), 5), '~', round(res.damage.max(), 5))
print('末帧损伤分布(前10节点):', [round(x,4) for x in res.damage[-1][:10]])
s = res.summary()
print('summary:')
for k, v in s.items():
    print(f'  {k}: {v}')
print("meta:")
for k, v in res.meta.items():
    print(f'  {k}: {v}')
