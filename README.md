# DND AI Assistant

一个面向 Dungeons & Dragons 跑团的纯 Python AI DM 助手原型。目标不是替代 DM，而是把“规则执行、战役状态、冒险生成、线索追踪、战斗回合、法术资源”等容易分心的部分交给工具，让玩家和主持人把注意力留给故事本身。

当前项目仍保持零外部依赖，安装和测试都只需要 Python 标准库。

## 当前能力

- D&D 5e 基础规则：骰子表达式、d20 检定、技能、豁免、攻击、暴击、伤害类型、抗性、易伤、免疫。
- 角色与怪物模型：属性、AC、HP、技能熟练、豁免熟练、状态、物品、法术位、已知法术、专注。
- 战斗系统：先攻排序、回合推进、行动/附赠动作/反应/移动资源、攻击、伤害结算、战斗中施法。
- 冒险数据结构：地点、NPC、线索、任务、遭遇、结局、地点可达性和线索门校验。
- AI 冒险生成：支持 mock provider 和 OpenAI-compatible provider，可接 OpenAI、DeepSeek、OpenRouter 或其他兼容 `/chat/completions` 的服务。
- 冒险运行时：可导入冒险 JSON 为 campaign state，并通过 `look`、`inspect`、`talk`、`go`、`fight`、`combat`、`attack`、`cast`、`end turn` 等动作推进。
- 规则检索 RAG：可从开放 SRD 构建本地 JSONL 语料，使用零依赖关键词/BM25 风格检索，为 AI DM 提供可追溯规则片段。
- 序列化与审查：campaign JSON 存档、冒险质量 review、文本/mermaid 地图输出。
- CI：GitHub Actions 自动运行测试。

## 快速开始

```powershell
cd F:\Work\dnd-ai-assistant
$env:PYTHONPATH = "src"
python -m unittest discover -s tests
```

安装本地命令：

```powershell
python -m pip install -e .
dnd-ai-assistant --help
```

也可以不安装，直接运行模块：

```powershell
python -m dnd_ai_assistant.demo quickstart
```

## 生成与导入冒险

创建一个冒险模板：

```powershell
python -m dnd_ai_assistant.demo new-adventure --output adventures\moonlit_road.json --title "Moonlit Road"
python -m dnd_ai_assistant.demo validate-adventure adventures\moonlit_road.json
python -m dnd_ai_assistant.demo review-adventure adventures\moonlit_road.json
python -m dnd_ai_assistant.demo adventure-map adventures\moonlit_road.json --format mermaid
python -m dnd_ai_assistant.demo import-adventure adventures\moonlit_road.json --output output\moonlit_campaign.json
```

用 AI 生成冒险前，可以先生成 prompt：

```powershell
python -m dnd_ai_assistant.demo adventure-prompt --premise "A bell rings under a ruined chapel." --party-level 2
```

使用 mock provider 做本地演示：

```powershell
python -m dnd_ai_assistant.demo generate-adventure `
  --provider mock `
  --mock-response ai_response.txt `
  --premise "A bell rings under a ruined chapel." `
  --adventure-output adventures\generated.json `
  --campaign-output output\generated_campaign.json
```

使用 OpenAI-compatible API：

```powershell
$env:DND_AI_BASE_URL = "https://api.deepseek.com"
$env:DND_AI_MODEL = "deepseek-chat"
$env:DND_AI_API_KEY = "<your api key>"

python -m dnd_ai_assistant.demo generate-adventure `
  --provider openai-compatible `
  --premise "A bell rings under a ruined chapel." `
  --party-level 2 `
  --player-count 4 `
  --duration-hours 3 `
  --tone "dark fantasy mystery" `
  --adventure-output adventures\generated.json `
  --campaign-output output\generated_campaign.json `
  --max-attempts 2 `
  --json-response-format
```

API key 只从环境变量读取，不从命令行参数读取，避免进入 shell 历史。

## 规则检索 RAG

第一版规则检索保持零外部依赖，默认使用开放 SRD 构建本地 JSONL 语料。生成的语料放在 `.dnd_ai/` 下，这个目录不会提交到仓库。

```powershell
python -m dnd_ai_assistant.demo build-rules-corpus `
  --source srd `
  --output .dnd_ai\rules\srd_5_2_1.jsonl
```

查询规则：

```powershell
python -m dnd_ai_assistant.demo search-rules `
  --corpus .dnd_ai\rules\srd_5_2_1.jsonl `
  --query "grapple attack action"
```

生成冒险时附加规则上下文：

```powershell
python -m dnd_ai_assistant.demo generate-adventure `
  --provider openai-compatible `
  --premise "A cursed tournament begins at midnight." `
  --adventure-output adventures\generated.json `
  --campaign-output output\generated_campaign.json `
  --rules-corpus .dnd_ai\rules\srd_5_2_1.jsonl
```

启动 API 时启用规则检索：

```powershell
python -m dnd_ai_assistant.demo serve-api `
  --host 127.0.0.1 `
  --port 8000 `
  --state-dir .dnd_ai\campaigns `
  --rules-corpus .dnd_ai\rules\srd_5_2_1.jsonl `
  --ai-provider openai-compatible
```

规则搜索 API：

```text
POST /rules/search
```

```json
{
  "query": "grapple attack action",
  "limit": 5
}
```

项目默认不提交 PHB 或第三方规则书原文。若以后需要使用你本机的中文 PHB，可以在本地私有目录导入为 JSONL，但不要把受限内容提交到公开仓库。

## 运行冒险

查看存档摘要：

```powershell
python -m dnd_ai_assistant.demo state-summary output\generated_campaign.json
```

非交互式推进：

```powershell
python -m dnd_ai_assistant.demo play-adventure-state output\generated_campaign.json `
  --seed 5 `
  --add-sample-character `
  --action "look" `
  --action "inspect" `
  --action "go old road" `
  --action "fight" `
  --action "combat" `
  --save-state output\generated_campaign.json
```

交互式运行：

```powershell
python -m dnd_ai_assistant.demo play-adventure-state output\generated_campaign.json --save-state output\generated_campaign.json
```

如果导入的冒险还没有玩家角色，可以加 `--add-sample-character` 自动加入一个可玩的 3 级牧师 Leth，包含 `Bless`、`Cure Wounds`、`Healing Word` 和 `Sacred Flame`。

生成一个不修改状态的 AI DM 建议：

```powershell
python -m dnd_ai_assistant.demo dm-suggest output\generated_campaign.json `
  --action "inspect the old altar" `
  --provider openai-compatible `
  --rules-corpus .dnd_ai\rules\srd_5_2_1.jsonl
```

`dm-suggest` 只生成叙述/裁定建议，不会写回 campaign state；实际检定、攻击、施法和移动仍由确定性 runtime action 执行。

常用动作：

```text
look
inspect
inspect ash
talk mayor
go old road
quests
complete quest missing travelers
fight
combat
attack goblin
cast bless
cast cure wounds leth
cast healing word
cast sacred flame goblin
use action
use bonus action
use reaction
spend movement 10
end turn
resolve encounter
log
quit
```

## 代码结构

- `src/dnd_ai_assistant/api.py`：零依赖 JSON API 雏形，供未来前端调用。
- `src/dnd_ai_assistant/core/dice.py`：骰子表达式解析与投骰。
- `src/dnd_ai_assistant/core/dnd5e.py`：D&D 5e 常用规则、检定、攻击与伤害。
- `src/dnd_ai_assistant/core/damage.py`：伤害类型、抗性、易伤、免疫调整。
- `src/dnd_ai_assistant/core/character.py`：角色模型。
- `src/dnd_ai_assistant/core/campaign.py`：战役、地点、NPC、线索、任务、遭遇、怪物。
- `src/dnd_ai_assistant/core/combat.py`：先攻、回合资源、战斗中施法。
- `src/dnd_ai_assistant/core/spells.py`：法术与法术位。
- `src/dnd_ai_assistant/core/serialization.py`：campaign JSON 存档。
- `src/dnd_ai_assistant/adventure.py`：冒险 JSON schema 与校验。
- `src/dnd_ai_assistant/adventure_generator.py`：AI 冒险 prompt、JSON 抽取、生成工作流。
- `src/dnd_ai_assistant/ai_provider.py`：可插拔 AI provider。
- `src/dnd_ai_assistant/adventure_importer.py`：冒险导入 campaign。
- `src/dnd_ai_assistant/adventure_runtime.py`：通用冒险运行时。
- `src/dnd_ai_assistant/adventure_review.py`：冒险质量审查。
- `src/dnd_ai_assistant/adventure_map.py`：地点图可视化。
- `src/dnd_ai_assistant/rules_corpus.py`：规则语料 JSONL、构建、检索与 prompt 上下文。
- `src/dnd_ai_assistant/ai_dm.py`：AI DM 建议生成，不直接修改 campaign state。
- `src/dnd_ai_assistant/demo.py`：CLI 入口。
- `tests/`：单元测试。

## API 雏形

当前 API 使用 Python 标准库 `http.server`，主要用于前端 MVP 前的接口验证：

```powershell
python -m dnd_ai_assistant.demo serve-api --host 127.0.0.1 --port 8000
```

已支持的端点：

```text
GET  /health
GET  /campaigns
POST /campaigns/import
POST /campaigns/demo
POST /campaigns/demo-with-character
GET  /campaigns/{campaign_id}
GET  /campaigns/{campaign_id}/summary
POST /campaigns/{campaign_id}/sample-character
POST /campaigns/{campaign_id}/actions
POST /campaigns/{campaign_id}/dm-suggestion
DELETE /campaigns/{campaign_id}
POST /rules/search
```

导入冒险时提交：

```json
{
  "adventure": {}
}
```

执行动作时提交：

```json
{
  "action": "inspect",
  "seed": 1
}
```

添加示例角色：

```text
POST /campaigns/{campaign_id}/sample-character
```

读取前端面板摘要：

```text
GET /campaigns/{campaign_id}/summary
```

创建内置 demo campaign：

```text
POST /campaigns/demo
POST /campaigns/demo-with-character
```

列出当前内存中的 campaign：

```text
GET /campaigns
```

删除当前内存中的 campaign：

```text
DELETE /campaigns/{campaign_id}
```

这层 API 目前是轻量桥接层，目标是先稳定前端需要的交互契约；后续可以替换为 FastAPI 或其他 Web 框架。

如果希望 API 重启后保留 campaign，可加 `--state-dir .dnd_ai\campaigns`。导入、添加示例角色、执行 runtime action 和删除 campaign 都会同步到这个本地目录。

## 前端 MVP

仓库包含一个零依赖的本地前端页面：

```text
web/index.html
```

使用方式：

1. 启动 API：

```powershell
python -m dnd_ai_assistant.demo serve-api --host 127.0.0.1 --port 8000
```

2. 在浏览器中打开 `web/index.html`。
3. 点击 `Start Demo`，或选择一个 adventure JSON 文件并导入。
4. 如果是手动导入，点击 `Add Sample Character`，然后用动作栏或输入框推进冒险。

当前页面支持 API 健康检查、列出/删除内存中的 campaign、内置 demo adventure、导入冒险、添加示例角色、查看摘要、发送 runtime action、AI DM 建议、规则搜索和查看 transcript。它是前端骨架，不需要 Node.js 或构建步骤。

## 近期路线

1. 继续完善 active combat：攻击目标选择、怪物行动模板、战斗结束条件、死亡/昏迷处理。
2. 扩展施法：法术攻击、豁免 DC、范围伤害、专注被打断、治疗法术。
3. 让 Adventure 和旧 Scene schema 收敛，减少两套格式并行。
4. 增强数据驱动 runtime action，让 AI 生成的冒险更少依赖硬编码。
5. 接入更完整的 AI DM 回合：根据 campaign state 生成叙述、建议检定、调用工具并写回状态。
6. 后续再做 Web API、多人房间、地图生成器、剧本创作工作台和持久化存储。

## 设计原则

- 先稳规则，再接复杂体验。
- 让 AI 生成内容，但让规则和状态由确定性代码执行。
- 保持 provider 可替换，成本优先时可使用 DeepSeek、OpenRouter 等 OpenAI-compatible 服务。
- 对玩家公开信息和 DM 私密信息保持分离。
- 每个功能都尽量有测试，避免跑团中途状态崩掉。
