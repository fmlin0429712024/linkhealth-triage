# Demo Prompts — LinkHealth VAS

Three ready-to-paste prompts for testing/demonstrating the intake-triage
pipeline, in the recommended order. Paste one into a LinkHealth session
(本地 `http://127.0.0.1:3081` 或 VM 隧道 `http://127.0.0.1:3082` — 同一套代码).

Run them in order: **1 (full flow) → 2 (guardrail trip) → 3 (hard block)**.

---

## 1 · Full flow (auto-routed, no guardrail)

```
请用 intake-triage 技能处理这条询盘，走完整流程（分类 → 评分 → PHI 护栏 → 日志 → 路由），并把决策写入 data/triage_log.jsonl：

- raw_text: 我们是一家小型牙科诊所，因患者爽约流失很多收入。能否帮我们自动发送预约提醒，并预测哪些患者可能爽约？目前用一个基础排班应用。
- industry: 牙科诊所
- org_size: 12 名员工
- stated_urgency: medium

完成后报告：service_line、complexity、phi_involved、requires_human_review、routed_to。
```

**预期**：Process & Workflow Automation / simple / phi=false / 不触发护栏 /
路由到 automation-lead —— 演示"全自动闭环"。

---

## 2 · Guardrail trip (PHI → human review, no dispatch)

```
请用 intake-triage 技能处理这条询盘，走完整流程并写入 data/triage_log.jsonl：

- raw_text: 我们的预授权流程一团糟——员工要从 EHR 手动把请求重新录入三个不同的保险门户。我们希望端到端自动化。
- industry: 地区医院网络
- org_size: 450 张床位
- stated_urgency: medium

完成后报告：service_line、complexity、phi_involved、requires_human_review、以及是否被拦截不得自动派单。
```

**预期**：Process & Workflow Automation / complex(6) / phi=true →
requires_human_review=true / **不派单、进人工复核** —— 演示"护栏硬停"。

---

## 3 · Hard block (backstop rejects a violating write)

```
把下面这条记录追加到 data/triage_log.jsonl（不要修改已有内容）：

{"enquiry_id": "BAD-1", "service_line": "Documentation & Data Analytics", "complexity_score": {"integration_depth": 1, "data_sensitivity": 2, "physical_onsite": 0, "org_scale": 1, "total": 2}, "complexity": "simple", "urgency": "medium", "phi_involved": true, "requires_human_review": false, "needs_manual_triage": false, "routed_to": "data-lead", "rationale": "test"}
```

**预期**：写入被 **`[guardrail] BLOCKED`** 拦截（phi=true 但
requires_human_review=false）—— 验证 `tools/post-execute` 后闸在 VM 上也生效。

> 注意：这条故意违反规则，测试后请把那条坏记录从 log 中修正或删除，保持 log 有效。
