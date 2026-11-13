import json,hashlib
def build_snapshot(records,inputs,outputs,sensitivity_count,benchmark,fixed_inputs=None):
    # 与v1保持同一键集合；仅当存在固定投入时才加入分类键，全可调整投入的研究序列化结果逐字节不变，指纹兼容。
    snapshot={'algorithm':'ccr-input-two-stage-v1','benchmark':benchmark,'records':records,'inputs':inputs,'outputs':outputs,'sensitivity_count':sensitivity_count,'baseline_self':True,'removal_policy':'same_R_minus_b_for_all_original_targets'}
    fixed=list(fixed_inputs or [])
    if fixed:
        if any(f not in inputs for f in fixed):raise ValueError('固定投入必须属于本次研究的投入维度')
        if len(fixed)==len(inputs):raise ValueError('全部投入均为固定投入时拒绝求解：至少保留一项可调整投入')
        snapshot['fixed_inputs']=fixed
        snapshot['adjustable_inputs']=[f for f in inputs if f not in fixed]
    return snapshot
def fingerprint_snapshot(snapshot):
    return hashlib.sha256(json.dumps(snapshot,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()
