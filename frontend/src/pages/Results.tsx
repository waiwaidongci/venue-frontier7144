import {useEffect,useState} from 'react';
import {useLocation} from '../router';
import {researchStore,loadResearch} from '../stores/research';
import {useTask} from '../hooks/useTask';
import {usePolling} from '../hooks/usePolling';
import {number} from '../utils/format';
import {fields} from '../constants/enums';
import PageHeading from '../components/common/PageHeading';
import ErrorNotice from '../components/common/ErrorNotice';
import EmptyState from '../components/common/EmptyState';
import StatusBadge from '../components/common/StatusBadge';
import EfficiencyPlot from '../components/EfficiencyPlot';
export default function Results(){
  const {query}=useLocation(),lab=researchStore.use();
  const [selected,setSelected]=useState(Number(query.get('run'))||0),[targetId,setTargetId]=useState(0);
  const {error,perform}=useTask();
  useEffect(()=>{perform(async()=>{await loadResearch();setSelected(id=>id||researchStore.get().runs[0]?.id||0);});},[perform]);
  useEffect(()=>{const id=Number(query.get('run'));if(id)setSelected(id);},[query.get('run')]);
  usePolling(async()=>{if(researchStore.get().runs.some(r=>r.id===selected&&['queued','running'].includes(r.status)))await loadResearch();});
  const run=lab.runs.find(r=>r.id===selected),rows=run?.result.baseline||[];
  const target=rows.find(r=>r.observation_id===targetId)||rows.find(r=>!r.strong_efficient)||rows[0];
  const fixedSet=new Set(run?.result.fixed_inputs||[]);
  const inputKeys=Object.keys(target?.input_slack||{});
  return <>
    <PageHeading index="04" title="把效率读成参照，把敏感性读成边界" text="λ是一组最优参照强度，不是概率；机构分数依赖本次共同参照集。"><a className="outline" href={`#/cases?run=${selected}&observation=${target?.observation_id||0}`}>记录改进假设 ↗</a></PageHeading>
    <ErrorNotice message={error} retry={()=>perform(loadResearch)}/>
    <div className="run-selector">
      <label>研究档案<select value={selected} onChange={e=>{setSelected(Number(e.target.value));setTargetId(0);}}>{lab.runs.map(r=><option key={r.id} value={r.id}>#{r.id} {r.name}</option>)}</select></label>
      {run&&<StatusBadge status={run.status}/>}
      <span>{run?.result.period} / 基线含自身{run?.result.fixed_inputs?.length?` / 固定${run.result.fixed_inputs.length}项 · 可调整${(run.result.adjustable_inputs||[]).length}项`:' / 全可调整投入'}</span>
    </div>
    {run?.status==='completed'&&target?<>
      <div className="result-layout">
        <EfficiencyPlot result={run.result} selected={target.observation_id} onSelect={setTargetId}/>
        <section className="target-sheet">
          <div className="target-selector"><label>目标机构<select value={target.observation_id} onChange={e=>setTargetId(Number(e.target.value))}>{rows.map(r=><option key={r.observation_id} value={r.observation_id}>{r.venue_code} / {r.venue_name}</option>)}</select></label></div>
          <div className="target-score"><span>径向效率 θ（仅作用于可调整投入）</span><strong>{number(target.theta,4)}</strong><small>{target.strong_efficient?'本次强有效参照':'仍有径向或松弛改进空间'}</small></div>
          <h3>最优参照组合</h3>
          <table><thead><tr><th>机构</th><th>强度 λ</th></tr></thead><tbody>{target.peers.map(p=><tr key={p.observation_id}><td>{p.venue_name}<small>{p.venue_code}{p.observation_id===target.observation_id?' / 自身':''}</small></td><td>{number(p.lambda,4)}</td></tr>)}</tbody></table>
          <p className="input-note">CCR允许Σλ≠1；多重最优解可能产生不同组合，这里展示求解器返回的一组。固定投入上限会改变这组参照的选择。</p>
          <h3>投入投影：可调整缩减与固定上限</h3>
          <table>
            <thead><tr><th>投入 / 口径</th><th>原值→参照组合用量</th><th>径向缩减</th><th>额外松弛 / 未占用空间</th></tr></thead>
            <tbody>{inputKeys.map(key=>{const isFixed=fixedSet.has(key);const legacy=target.radial_reduction===undefined;return <tr key={key} className={isFixed?'fixed-input-row':''}>
              <td><b>{fields[key]||key}</b><small>{isFixed?'固定投入 · 不给压缩建议':'可调整投入'}</small></td>
              <td>{number(target.source[key],1)} → {number(target.projected_inputs[key],1)}</td>
              <td>{isFixed?'—（不随θ压缩）':number(legacy?0:target.radial_reduction?.[key],2)}</td>
              <td>{isFixed?`未占用 ${number(target.fixed_headroom?.[key]??0,2)}（仅上限约束）`:number(target.input_slack[key],2)}</td>
            </tr>;})}</tbody>
          </table>
          <p className="input-note">可调整投入：投影=θX₀−额外松弛，径向缩减(1−θ)X₀与额外松弛分别呈现。固定投入：仅要求 ΣλX ≤ X₀，投影是参照组合实际用量，差额是未占用空间而非削减建议。产出盈余：{Object.entries(target.output_slack).map(([k,v])=>fields[k]+' '+number(v,2)).join('；')}。</p>
        </section>
      </div>
      <section className="sensitivity-section">
        <div className="section-heading"><h2>共同标杆逐一移除</h2><span>原目标集不变 / 每情景共享同一R减b</span></div>
        <p className="method-line">被移除标杆也继续接受评估，其自身被排出参照后可能θ&gt;1。各移除情景沿用同一固定/可调整投入分类。θ升高不代表实际表现改善；不可行或无界显示原状态。</p>
        <div className="table-wrap"><table><thead><tr><th>移除标杆</th><th>外部累计 λ</th><th>参照机构</th><th>{target.venue_code} 新θ</th><th>Δθ</th><th>目标自身被移除</th></tr></thead><tbody>{run.result.scenarios?.map(s=>{const score=s.scores.find(r=>r.observation_id===target.observation_id);return <tr key={s.removed_observation_id}><td><b>{s.removed_name}</b><small>{s.removed_code}</small></td><td>{number(s.aggregate_external_lambda,3)}</td><td>{s.reference_ids.length}馆</td><td>{score?.status==='optimal'?number(score.theta,4):score?.status}</td><td>{number(score?.delta,4)}</td><td>{score?.removed_target_self?'是 / 超效率式反事实':'否 / 其余参照含自身'}</td></tr>;})}</tbody></table></div>
      </section>
      <p className="fingerprint">INPUT SHA256 / {run.result.fingerprint}</p>
    </>:<EmptyState title={run?.status==='failed'?'求解未完成':'等待效率求解'} text={run?.error||'运行中状态会自动刷新；请选择一个已完成研究，或先建立同期参照集。'}/>}
  </>;
}
