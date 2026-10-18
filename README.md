# agent-skills

冯金岳（Feng Jinyue）的 Agent Skill 合集。每个 skill 都是自包含的文件夹（`SKILL.md` + 脚本/参考/资源），遵循开放的 [Agent Skills 规范](https://agentskills.io)——同一份 skill 可在 WorkBuddy、Claude Code、Codex、Cursor 等支持该规范的宿主中使用。

> 🌐 移动端友好的介绍页（适合分享给手机用户）：**https://greenwich-art.github.io/agent-skills**

## Skill 索引

| Skill | 版本 | 能力 | 独立子库 |
|---|---|---|---|
| [macos-vision-ocr](skills/macos-vision-ocr/) | 2.1.0 | macOS 内置 Vision 框架本地 OCR：免费、离线、零依赖，竖排检测/方向纠正/小图放大 | [skill-macos-vision-ocr](https://github.com/GreenWich-art/skill-macos-vision-ocr) |
| [gbt7714-reference-check](skills/gbt7714-reference-check/) | 1.0.0 | GB/T 7714-2015 参考文献著录规范化 + URL/DOI/PMID/PMC 链接批量核验与「假失效」识别 | [skill-gbt7714-reference-check](https://github.com/GreenWich-art/skill-gbt7714-reference-check) |
| [docx-academic-format](skills/docx-academic-format/) | 1.0.0 | 中文学术论文 docx 批量排版：三线表（1/8 磅）、统计量斜体、中西文混排四槽位 | [skill-docx-academic-format](https://github.com/GreenWich-art/skill-docx-academic-format) |
| [pubmed-lit-report](skills/pubmed-lit-report/) | 1.0.1 | PubMed/EuropePMC 检索 → 双语 HTML 报告 → OA PDF 下载 → 7 项质量门禁的一站式流水线 | [skill-pubmed-lit-report](https://github.com/GreenWich-art/skill-pubmed-lit-report) |
| [desktop-takeover](skills/desktop-takeover/) | 1.3.1 | 桌面 GUI 操作统一编排：五级路由决策、macOS 授权引导、任务三段式派发、AX 兜底工具 | [skill-desktop-takeover](https://github.com/GreenWich-art/skill-desktop-takeover) |
| [pmc-oa-pdf-fetch](skills/pmc-oa-pdf-fetch/) | 1.0.0 | 开放获取文献 PDF/补充材料下载，含 PMC PoW 离线求解与出版社拦截绕行 | [skill-pmc-oa-pdf-fetch](https://github.com/GreenWich-art/skill-pmc-oa-pdf-fetch) |

## 安装单个 skill（三种方式，任选其一）

**方式一：npx skills CLI（推荐，自动识别 69+ 种 agent 宿主）**

```bash
# 从独立子库装（等价于从总库单装）
npx skills add GreenWich-art/skill-macos-vision-ocr

# 或从总库按名字单装
npx skills add GreenWich-art/agent-skills --skill macos-vision-ocr

# 装到用户级目录（跨项目可用）
npx skills add GreenWich-art/skill-macos-vision-ocr -g
```

**方式二：下载 zip**

到对应子库（或本库 Releases）下载 `<skill>-v<版本>.zip`，解压后把整个 skill 文件夹放进宿主的 skills 目录：

| 宿主 | 用户级目录 | 项目级目录 |
|---|---|---|
| WorkBuddy | `~/.workbuddy/skills/` | `<项目>/.workbuddy/skills/` |
| Claude Code | `~/.claude/skills/` | `<项目>/.claude/skills/` |
| Codex | `~/.codex/skills/` | `<项目>/.codex/skills/` |

注意：解压后应是 `skills/<skill名>/SKILL.md` 这一层，不要多套目录。

**方式三：Claude Code 插件市场**

```text
/plugin marketplace add GreenWich-art/agent-skills
```

然后按名字安装单个插件（每个 skill 已注册为独立插件）。

## 使用

装好后直接对 agent 描述任务即可，skill 会按 `SKILL.md` 里的触发词自动激活；也可以显式点名（如「用 macos-vision-ocr 识别这张图」）。各 skill 的详细用法见其目录内的 `README.md`。

## 仓库结构

```text
agent-skills/                ← 总库（唯一事实源，未来新 skill 都加进 skills/）
├── skills/<name>/           ← 每个 skill 自包含（SKILL.md + scripts/references/tools/assets）
├── scripts/split-repos.sh   ← 一键把各 skill 镜像推送到独立子库
└── .claude-plugin/          ← Claude Code 插件市场注册文件

skill-<name>/                ← 独立子库 × N（split-repos.sh 自动生成的只读镜像）
```

**贡献**：请直接向总库提 PR/Issue；子库是自动镜像，不接受直接提交。本地维护流程：改 `skills/<name>/` → 提交推送总库 → 运行 `sh scripts/split-repos.sh` 同步子库 → 在子库打 tag 发 Release 附 zip。

## License

总库以 MIT 发布（见 [LICENSE](LICENSE)）；每个 skill 目录内另有各自的 MIT LICENSE，作者均为冯金岳 (Feng Jinyue)。
