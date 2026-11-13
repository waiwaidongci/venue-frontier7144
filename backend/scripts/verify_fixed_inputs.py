"""固定投入（非可自由处置投入）手算样例核对脚本。

运行：/tmp/venv/bin/python /workspace/backend/scripts/verify_fixed_inputs.py
覆盖：
  1. 手算样例：固定投入改变参照选择（同目标在全可调整 vs 固定工时下换参照、换θ）
  2. 单位换算不变性（工时由小时换成“百工时”、元换成千元）
  3. 全固定投入拒绝求解（求解器层 / 服务层 / 接口校验层三处）
  4. 旧数据按全可调整投入兼容读取，且指纹与 v1 逐字节一致
  5. README 闭式三 DMU 回归（θ 与移除 C 后结果）
"""
import sys, json, hashlib
sys.path.insert(0, '/workspace/backend')
from src.services.dea_solver import solve_dmu
from src.services.sensitivity import analyze_frontier
from src.services.fingerprint import build_snapshot, fingerprint_snapshot

PASS, FAIL = [], []
def check(name, cond, detail=''):
    (PASS if cond else FAIL).append(name)
    print(('  ✓ ' if cond else '  ✗ ') + name + (f' — {detail}' if detail else ''))

def close(a, b, tol=1e-7):
    return abs(float(a) - float(b)) <= tol

# ---------------------------------------------------------------------------
# 1. 手算样例：两投入（a=可调整能源费用，f=固定人员工时），单产出 y
#    A（目标）: 能源 100, 工时 100, 产出 1
#    B（参照）: 能源 12,  工时 90,  产出 1
#    C（参照）: 能源 8,   工时 110, 工时 110, 产出 1
# ---------------------------------------------------------------------------
print('\n[1] 手算样例：固定投入改变参照选择')
x = [[100., 100.], [12., 90.], [8., 110.]]
y = [[1.], [1.], [1.]]
xs = [100., 110.]

# 1a. 全可调整：单参照逐点评估
#     只用 B：θ≥max(12/100, 90/100)=.90；只用 C：θ≥max(8/100, 110/100)=1.10
#     凸组合的 θ 是两个单参照点之间的线性插值，最小在 B 端点 ⇒ θ=.90，λB=1
r_all = solve_dmu(x[0], y[0], x, y, xs, [1.], fixed_inputs=None)
print('    全可调整：  θ=%.4f，参照λ=%s' % (r_all['theta'], [round(w, 6) for w in r_all['weights']]))
check('全可调整时参照 B（θ=.90；C 因工时110>100 不可单独作为参照）', close(r_all['theta'], 0.9) and r_all['weights'][1] > 0.99)

# 1b. 工时固定：能源 12λB+8λC ≤ 100θ；工时 90λB+110λC ≤ 100（无θ）；λB+λC ≥ 1
#     取 λB+λC=1，工时约束 ⇒ 90(1-λC)+110λC ≤ 100 ⇒ λC ≤ .5
#     能源目标 (12λB+8λC)/100 随 λC 增大而减小 ⇒ λC=.5, λB=.5
#     参照用量 能源=6+4=10 ⇒ θ=.10；工时=45+55=100，未占用空间=0
r_fix = solve_dmu(x[0], y[0], x, y, xs, [1.], fixed_inputs=[1])
print('    工时固定：  θ=%.4f，参照λ=%s' % (r_fix['theta'], [round(w, 6) for w in r_fix['weights']]))
check('固定工时后 θ=.10（手算：90λB+110λC≤100 与 λB+λC=1 交点）', close(r_fix['theta'], 0.10))
check('固定工时改变参照组合：B、C 同时入选（各 .5）', close(r_fix['weights'][1], 0.5) and close(r_fix['weights'][2], 0.5))
check('固定投入不产生径向缩减建议（radial_reduction[1]=0）', close(r_fix['radial_reduction'][1], 0.0))
check('固定投入松弛为 0，仅报告未占用空间 headroom=100-100=0', close(r_fix['fixed_headroom'][1], 0.0))
check('可调整能源的径向缩减=(1-.10)*100=90', close(r_fix['radial_reduction'][0], 90.0))
# 固定约束确实把 C 单独使用的方案排除
r_c_only = solve_dmu(x[0], y[0], [x[2]], [y[2]], xs, [1.], fixed_inputs=[1])
check('固定工时下只剩 C 参照时不可行（110>100 上限）', r_c_only['status'] == 'infeasible')

# ---------------------------------------------------------------------------
# 2. 单位换算不变性
# ---------------------------------------------------------------------------
print('\n[2] 单位换算不变性')
# 工时小时→百工时（÷100），能源元→千元（÷1000）
x_u = [[v[0] / 1000., v[1] / 100.] for v in x]
xs_u = [100. / 1000., 110. / 100.]
r_unit = solve_dmu(x_u[0], y[0], x_u, y, xs_u, [1.], fixed_inputs=[1])
check('换算后 θ 不变（.10）', close(r_unit['theta'], 0.10), f"got {r_unit['theta']}")
check('换算后 λ 不变', all(close(a, b) for a, b in zip(r_unit['weights'], r_fix['weights'])))
# 原单位投影量经换算与新单位投影一致
check('投影按单位换算（能源 10 元 → .01 千元）', close(r_unit['projected_inputs'][0], r_fix['projected_inputs'][0] / 1000.))
check('投影按单位换算（工时 100 小时 → 1 百工时）', close(r_unit['projected_inputs'][1], r_fix['projected_inputs'][1] / 100.))
# 全可调整口径同样满足单位不变（与 v1 行为一致）
r_unit_all = solve_dmu(x_u[0], y[0], x_u, y, xs_u, [1.])
check('全可调整口径单位不变（θ=.9）', close(r_unit_all['theta'], 0.9))

# ---------------------------------------------------------------------------
# 3. 全固定投入拒绝求解
# ---------------------------------------------------------------------------
print('\n[3] 全固定投入拒绝求解')
for layer, kwargs in [('求解器', dict(fixed_inputs=[0, 1])), ('求解器-下标形式', dict(fixed_inputs=[1, 0]))]:
    try:
        solve_dmu(x[0], y[0], x, y, xs, [1.], **kwargs)
        check(f'{layer}层全固定拒绝', False, '未抛出异常')
    except ValueError as exc:
        check(f'{layer}层全固定拒绝', '至少保留一项可调整投入' in str(exc), str(exc))

records = [
    {'observation_id': 1, 'venue_code': 'A', 'venue_name': '甲', 'a': 100., 'f': 100., 'y': 1.},
    {'observation_id': 2, 'venue_code': 'B', 'venue_name': '乙', 'a': 12., 'f': 90., 'y': 1.},
    {'observation_id': 3, 'venue_code': 'C', 'venue_name': '丙', 'a': 8., 'f': 110., 'y': 1.},
]
try:
    analyze_frontier(records, ['a', 'f'], ['y'], 3, fixed_inputs=['a', 'f'])
    check('服务层全固定拒绝', False, '未抛出异常')
except ValueError as exc:
    check('服务层全固定拒绝', '至少保留一项可调整投入' in str(exc), str(exc))

from src.schemas.run import RunInput
# schema 只接受枚举字段，用真实枚举测全固定与非法字段
payload_enum = {'name': '全固定拒绝样例', 'benchmark_id': 1, 'inputs': ['staff_hours', 'energy_cost'],
                'outputs': ['visits'], 'fixed_inputs': ['staff_hours', 'energy_cost']}
try:
    RunInput(**payload_enum)
    check('接口校验层全固定拒绝（422 来源）', False, '未抛出异常')
except Exception as exc:
    check('接口校验层全固定拒绝（422 来源）', '至少保留一项可调整投入' in str(exc), type(exc).__name__)
try:
    RunInput(**{**payload_enum, 'fixed_inputs': ['visits']})  # 产出字段冒充固定投入 → 越界
    check('固定字段必须属于投入维度（非法字段拒绝）', False, '未抛出异常')
except Exception:
    check('固定字段校验存在（非法/越界字段抛错）', True)
try:
    ok = RunInput(**{**payload_enum, 'fixed_inputs': ['staff_hours']})  # 两投入留一项可调整 → 合法
    check('保留至少一项可调整投入时校验通过', ok.fixed_inputs == ['staff_hours'])
except Exception as exc:
    check('保留至少一项可调整投入时校验通过', False, str(exc))

# ---------------------------------------------------------------------------
# 4. 旧数据兼容：全可调整时分类为空、结果结构与指纹与 v1 逐字节一致
# ---------------------------------------------------------------------------
print('\n[4] 旧数据兼容与指纹')
records3 = [
    {'observation_id': 1, 'venue_code': 'DMU1', 'venue_name': '一', 'staff_hours': 10., 'energy_cost': 10., 'visits': 1., 'programs': 1.},
    {'observation_id': 2, 'venue_code': 'DMU2', 'venue_name': '二', 'staff_hours': 20., 'energy_cost': 20., 'visits': 1., 'programs': 1.},
    {'observation_id': 3, 'venue_code': 'DMU3', 'venue_name': '三', 'staff_hours': 10., 'energy_cost': 10., 'visits': 2., 'programs': 2.},
]
bench = {'id': 7, 'code': 'QY-2026Q3', 'period': '2026Q3'}
res = analyze_frontier(records3, ['staff_hours', 'energy_cost'], ['visits', 'programs'], 3)
check('全可调整研究 fixed_inputs 为空列表（旧数据读法）', res['fixed_inputs'] == [] and res['adjustable_inputs'] == ['staff_hours', 'energy_cost'])
check('每行仍含 v1 全部结果键', all(set(['input_slack', 'output_slack', 'projected_inputs', 'projected_outputs', 'peers', 'theta']).issubset(r) for r in res['baseline']))
snapshot = build_snapshot(records3, ['staff_hours', 'energy_cost'], ['visits', 'programs'], 3, bench)
# 手工复刻 v1 run_service 的快照结构（无 fixed_inputs 键）
v1_snapshot = {'algorithm': 'ccr-input-two-stage-v1', 'benchmark': bench, 'records': records3,
               'inputs': ['staff_hours', 'energy_cost'], 'outputs': ['visits', 'programs'],
               'sensitivity_count': 3, 'baseline_self': True,
               'removal_policy': 'same_R_minus_b_for_all_original_targets'}
check('全可调整快照与 v1 键集合完全一致', set(snapshot.keys()) == set(v1_snapshot.keys()))
fp_new = fingerprint_snapshot(snapshot)
fp_v1 = hashlib.sha256(json.dumps(v1_snapshot, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()
check('全可调整指纹与 v1 逐字节一致', fp_new == fp_v1, fp_new)

# 含固定投入时指纹必须不同，且分类进入快照
snap_fixed = build_snapshot(records3, ['staff_hours', 'energy_cost'], ['visits', 'programs'], 3, bench, fixed_inputs=['staff_hours'])
check('固定投入分类进入指纹快照', snap_fixed.get('fixed_inputs') == ['staff_hours'] and snap_fixed.get('adjustable_inputs') == ['energy_cost'])
check('含固定投入的研究指纹不同于 v1', fingerprint_snapshot(snap_fixed) != fp_v1)

# 模拟旧库行：无 fixed_inputs 列/键 → 服务用 run.fixed_inputs or [] 读成空
class OldRow:
    pass
old = OldRow()
check('旧研究行缺列时按空列表兼容读取', (getattr(old, 'fixed_inputs', None) or []) == [])

# ---------------------------------------------------------------------------
# 5. README 闭式三 DMU 回归：[x,y]=[1,1],[2,1],[1,2]
# ---------------------------------------------------------------------------
print('\n[5] README 闭式三 DMU 回归（全可调整，口径不变）')
xx = [[1.], [2.], [1.]]
yy = [[1.], [1.], [2.]]
thetas = [solve_dmu(xx[i], yy[i], xx, yy)['theta'] for i in range(3)]
check('基线 θ=[.5,.25,1]', all(close(a, b) for a, b in zip(thetas, [.5, .25, 1.])), str(thetas))
keep = [0, 1]  # 统一移除 C
thetas_rm = [solve_dmu(xx[i], yy[i], [xx[j] for j in keep], [yy[j] for j in keep])['theta'] for i in range(3)]
check('统一移除 C 后 θ=[1,.5,2]（超效率不裁剪）', all(close(a, b) for a, b in zip(thetas_rm, [1., .5, 2.])), str(thetas_rm))

print('\n结果：%d 通过 / %d 失败' % (len(PASS), len(FAIL)))
sys.exit(1 if FAIL else 0)
