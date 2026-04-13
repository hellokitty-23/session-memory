# Contributing

欢迎提交 issue 和 pull request。

## Development Guidelines

- 文档、注释和说明建议使用中文；代码与技术标识保持英文。
- 优先复用现有脚本入口，不新增重复命令层。
- 不要提交运行时产物、缓存文件、本地日志和 `.codex/` 数据。
- 涉及行为变更时，请同步更新 `README.md`、`SKILL.md` 或模板文件。

## Suggested Checks

提交前建议至少检查：

```bash
python3 -m py_compile scripts/*.py
```

如果修改了模板或说明文档，也请手动验证示例命令是否仍然可用。
