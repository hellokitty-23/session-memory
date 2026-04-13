# Contributing

中文：欢迎提交 issue 和 pull request。  
English: Issues and pull requests are welcome.

## 开发约定 | Development Guidelines

- 优先复用现有脚本入口，不新增重复命令层。 | Reuse existing script entry points instead of adding duplicate command layers.
- 不要提交运行时产物、缓存文件、本地日志和 `.codex/` 数据。 | Do not commit runtime outputs, cache files, local logs, or `.codex/` data.
- 涉及行为变更时，请同步更新 `README.md`、`SKILL.md` 或模板文件。 | If behavior changes, update `README.md`, `SKILL.md`, or template files accordingly.

## 建议检查 | Suggested Checks

中文：提交前建议至少检查：  
English: Before submitting, it is recommended to run at least:

```bash
python3 -m py_compile scripts/*.py
```

中文：如果修改了模板或说明文档，也请手动验证示例命令是否仍然可用。  
English: If you changed templates or documentation, also verify that the example commands still make sense.
