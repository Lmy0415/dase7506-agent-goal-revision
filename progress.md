# 实验进度

更新日期 2026-11-24。正式任务清单未冻结，模型调用 0 次，模型费用 0 美元。

## 阶段 0 · 私有仓库

已核验 GitHub 身份为 `Lmy0415`，并创建 [私有仓库](https://github.com/Lmy0415/dase7506-agent-goal-revision)。默认分支为 `main`。

本地目录为 `/Users/jeff/Desktop/DASE_7506/Project/dase7506-agent-goal-revision`。

## 阶段 1 · 题库与运行边界

已固定两套上游源码版本，见 README。InterventionBench v1.1 的 AppWorld JSONL
含 1,197 条，其中 1,088 条未被上游标记排除。Swap 393 条，部分 Drop 100 条，
有修订目标和终态评估代码的两类候选覆盖 131 个不同基础任务。符合本实验
中断与写入可观测标准的题量待实测。

上游默认分支的 `results/` 只含说明和汇总结果，仓库 Release 列表为空。
运行 `python3 scripts/eval.py --results results --data data --output /tmp/recomputed.json`
输出 0 个模型/环境结果，尚无公开原始轨迹可供这一入口复算。
