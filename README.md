# DND AI 跑团助手

一个面向 Dungeons & Dragons 跑团的 AI 辅助主持工具。项目目标是帮助没有 DM 经验的玩家快速开始一场可玩的 DND 冒险，并在跑团过程中提供剧情推进、NPC 扮演、规则辅助、骰子判定、战役记录和设定管理。

本项目优先服务 DND 场景，后续可以扩展到 COC、PF2e 或自定义规则系统。

## 项目愿景

很多玩家想玩 DND，但卡在几个现实问题上：

- 没有人愿意或有经验当 DM
- 准备世界观、剧情、NPC、地图和遭遇很耗时
- 新手不熟悉规则、检定、战斗和法术
- 跑团过程中容易忘记线索、NPC 态度、任务状态和历史事件
- AI 聊天工具可以写剧情，但缺少规则约束、长期记忆和游戏状态管理

本项目希望做成一个“AI DM + 战役工作台”：

- 跑团前：根据灵感生成完整冒险模组
- 跑团中：AI 扮演 DM，描述场景、扮演 NPC、建议检定、调用骰子、记录状态
- 跑团后：自动整理日志、线索、战利品、经验和下一章伏笔

## 核心原则

1. **DND 优先**
   第一版以 DND 5e 风格为主，先覆盖常见检定、角色状态、战斗轮次、NPC 和遭遇设计，不一开始追求完整复刻所有规则书。

2. **AI 不直接编骰子**
   AI 可以判断“这里需要一个敏捷豁免”或“进行一次察觉检定”，但实际骰子结果必须由程序生成并记录。

3. **AI 不控制玩家角色**
   AI 可以描述后果、环境和 NPC 行动，但不能替玩家决定角色说什么、做什么、攻击谁或是否接受任务。

4. **区分玩家可见信息和 DM 秘密**
   世界设定、伏笔、隐藏线索、怪物真实身份、幕后黑手等必须分层存储。AI 在玩家视角输出时不能提前剧透。

5. **状态优先于长聊天**
   重要信息要落到结构化状态里，而不是只存在聊天记录中。例如角色 HP、法术位、位置、任务进度、NPC 态度、已获得线索。

6. **先能跑一晚，再追求宏大**
   第一阶段目标是稳定支持 2 到 4 名玩家完成一场 2 到 3 小时的短团。

## MVP 范围

第一版建议做成 Web App，先支持一个小队、一名 AI DM、一个战役房间。

## 当前原型

当前仓库已经从 DND 核心工具层开始实现，重点是让未来 AI DM 调用确定性的规则工具，而不是自己编结果。

已包含：

- `src/dnd_ai_assistant/core/dice.py`
  - 解析和投掷 `1d20`、`2d6+3`、`d8-1` 等骰子表达式
- `src/dnd_ai_assistant/core/dnd5e.py`
  - 属性修正值
  - 熟练加值
  - 普通 / 优势 / 劣势 d20 检定
  - 伤害骰
  - 简单攻击命中和伤害结算
- `src/dnd_ai_assistant/core/initiative.py`
  - 简单先攻排序和回合推进
- `src/dnd_ai_assistant/core/character.py`
  - 简化 DND 角色状态
  - HP、AC、属性、熟练、豁免、伤害和治疗
- `src/dnd_ai_assistant/core/campaign.py`
  - 战役、地点、NPC、线索、任务、遭遇、怪物、事件日志等结构化模型
- `src/dnd_ai_assistant/core/dm_tools.py`
  - AI DM 未来可调用的工具层：创建战役、添加地点/NPC/线索、揭示线索、记录事件、执行检定、应用伤害和治疗
- `src/dnd_ai_assistant/demo.py`
  - 当前版本的命令行演示入口
- `src/dnd_ai_assistant/scene_engine.py`
  - 场景运行引擎：根据场景 JSON、玩家行动、检定和状态推进短场景
- `tests/test_core.py`
  - 核心规则的最小单元测试
- `tests/test_dm_tools.py`
  - 战役工具层的最小单元测试
- `tests/test_demo.py`
  - 命令行演示流程的最小测试

运行测试：

```powershell
cd F:\work\dnd-ai-assistant
$env:PYTHONPATH = "src"
python -m unittest discover -s tests
```

也可以以可编辑模式安装本地命令：

```powershell
cd F:\work\dnd-ai-assistant
python -m pip install -e .
dnd-ai-assistant --help
```

运行当前 demo：

```powershell
cd F:\work\dnd-ai-assistant
$env:PYTHONPATH = "src"
python -m dnd_ai_assistant.demo quickstart
```

运行先攻演示：

```powershell
python -m dnd_ai_assistant.demo initiative
python -m dnd_ai_assistant.demo initiative --seed 42 --rounds 3
python -m dnd_ai_assistant.demo initiative --scene path\to\your_scene.json
```

指定随机种子，方便复现实验结果：

```powershell
python -m dnd_ai_assistant.demo quickstart --seed 42
```

这个 demo 会创建一个示例战役，加入一名游侠角色、一个地点、一个 NPC、一个线索和一个任务，然后进行一次带优势的察觉检定，并打印 session log。

运行一个极简交互场景：

```powershell
python -m dnd_ai_assistant.demo play
```

可以输入：

```text
look around
inspect rope
open stairway
log
quit
```

默认场景也支持少量中文触发词，例如：

```text
观察四周
检查钟绳
打开楼梯
退出
```

也可以用非交互方式脚本化运行，方便测试：

```powershell
python -m dnd_ai_assistant.demo play --action "look around" --action "inspect rope" --action "open stairway" --action "quit"
```

当前默认场景来自：

```text
src/dnd_ai_assistant/scenes/old_chapel.json
```

也可以指定自己的场景 JSON：

```powershell
python -m dnd_ai_assistant.demo play --scene path\to\your_scene.json
```

校验场景 JSON：

```powershell
python -m dnd_ai_assistant.demo validate-scene
python -m dnd_ai_assistant.demo validate-scene --scene path\to\your_scene.json
```

生成一个新的场景模板：

```powershell
python -m dnd_ai_assistant.demo new-scene --output scenes\my_adventure.json --title "Goblin Road"
```

现在的场景 JSON 还很小，只覆盖一个地点、一个 NPC、一个线索、一个任务、一个遭遇和一个固定检定。它的意义是把“剧本内容”和“跑团引擎”分开，后续 AI 生成的剧本可以按同样格式落盘。
动作触发词在 JSON 的 `actions` 字段中配置。

保存一次跑团后的战役状态：

```powershell
python -m dnd_ai_assistant.demo play --action "inspect rope" --action "open stairway" --action "quit" --save-state output\ashford_state.json
```

查看保存后的状态摘要：

```powershell
python -m dnd_ai_assistant.demo state-summary output\ashford_state.json
```

保存的状态包含战役基础信息、角色、地点、NPC、线索、任务和 session log。相关代码在：

```text
src/dnd_ai_assistant/core/serialization.py
```

当前版本可以作为 Python 库手动调用。例如：

```powershell
cd F:\work\dnd-ai-assistant
$env:PYTHONPATH = "src"
python
```

然后在 Python 里运行：

```python
import random
from dnd_ai_assistant.core.character import Character
from dnd_ai_assistant.core.dm_tools import DMTools
from dnd_ai_assistant.core.dnd5e import RollMode

tools = DMTools(rng=random.Random(1))
campaign = tools.create_campaign(
    title="The Bell Beneath Ashford",
    party_level=2,
    tone="dark fantasy investigation",
).data

hero = Character(
    name="Kael",
    player_name="Altman",
    class_name="Ranger",
    level=2,
    ancestry="Wood Elf",
    ability_scores={"str": 10, "dex": 16, "con": 12, "int": 10, "wis": 14, "cha": 8},
    armor_class=15,
    max_hp=18,
    current_hp=18,
    skill_proficiencies={"perception"},
    saving_throw_proficiencies={"str", "dex"},
)

tools.add_character(campaign.id, hero)
chapel = tools.add_location(
    campaign.id,
    name="Old Chapel",
    public_description="A cracked chapel with a silent bronze bell.",
).data
clue = tools.add_clue(
    campaign.id,
    title="Ash on the Bell Rope",
    public_text="The rope is dusted with black ash.",
    location_id=chapel.id,
).data

tools.reveal_clue(campaign.id, clue.id)
check = tools.roll_check(
    campaign.id,
    character_name="Kael",
    modifier=5,
    dc=15,
    mode=RollMode.ADVANTAGE,
).data

print(check.total, check.success)
print([event.content for event in campaign.session_log])
```

### 1. 战役创建

用户输入：

- 冒险主题，例如“被遗忘矿镇中的龙裔诅咒”
- 风格：英雄奇幻、黑暗奇幻、轻松冒险、地下城探索、城市阴谋
- 玩家人数
- 角色等级
- 游戏时长：一晚短团、三章短战役、长期战役开篇
- 战斗比例：低、中、高
- 谜题比例：低、中、高
- 是否需要官方 DND 风格，但避免直接复制受版权保护的官方模组文本

AI 生成：

- 冒险标题
- 背景概述
- 开场钩子
- 主要地点
- 关键 NPC
- 敌对势力
- 主线目标
- 支线任务
- 遭遇列表
- 宝物和奖励
- 结局分支
- DM 秘密
- 玩家可见导入文本

### 2. 角色卡

第一版角色卡只做跑团必需字段：

- 角色名
- 玩家名
- 种族/职业/等级
- 属性值与修正值
- 熟练加值
- AC
- HP / 最大 HP
- 速度
- 技能熟练
- 豁免熟练
- 武器/攻击动作
- 法术位和常用法术
- 装备
- 背景与人物关系
- 当前状态：倒地、中毒、魅惑、专注等

### 3. 骰子与判定

必须由程序执行：

- `1d20`
- `1d20 + 属性修正 + 熟练加值`
- 优势 / 劣势
- 攻击检定
- 伤害骰
- 属性检定
- 技能检定
- 豁免检定
- 先攻
- 死亡豁免

AI 的职责：

- 判断是否需要检定
- 给出建议 DC
- 说明成功、失败、大成功、大失败的叙事后果

### 4. AI DM 聊天

AI DM 应该能：

- 描述场景
- 扮演 NPC
- 管理信息公开程度
- 接受玩家行动
- 判断是否需要检定
- 调用骰子工具
- 根据结果推进剧情
- 记录关键事件
- 在玩家偏离主线时自然地重接线索
- 在战斗中管理怪物行动和回合顺序

AI DM 不应该：

- 替玩家做选择
- 直接修改骰子结果
- 临时改变已公开设定
- 提前透露隐藏信息
- 跳过关键玩家决策

### 5. 战役资料库

资料分层：

- `public_lore`：玩家可见设定
- `dm_secrets`：只有 DM/AI 可见的秘密
- `locations`：地点
- `npcs`：NPC
- `factions`：势力
- `quests`：任务
- `clues`：线索
- `encounters`：遭遇
- `items`：物品
- `session_log`：跑团记录
- `current_state`：当前状态

### 6. 地图和关系图

第一版不做复杂 3D 或精美战棋地图，先做三类轻量视图：

- 地点关系图：城镇、地下城房间、野外区域之间的连接
- 战斗网格：简单方格、角色 token、怪物 token、障碍物
- 线索板：线索、NPC、地点、任务之间的关系

## 推荐技术路线

### 前端

- Next.js
- React
- TypeScript
- Tailwind CSS
- Zustand 或 Redux Toolkit 管理客户端状态
- React Flow 绘制地点图/线索图

### 后端

- Python FastAPI 或 Node.js/NestJS
- PostgreSQL
- pgvector 用于设定和日志检索
- WebSocket 用于多人房间实时同步

### AI 层

- OpenAI Responses API 或 Agents SDK
- 工具调用：
  - `roll_dice`
  - `get_character`
  - `update_character`
  - `search_lore`
  - `record_event`
  - `reveal_clue`
  - `start_encounter`
  - `advance_turn`
  - `generate_npc`
  - `generate_location`

### 数据格式

AI 生成内容应尽量使用结构化 JSON，再由前端渲染成卡片、地图和文本。

示例：

```json
{
  "adventure": {
    "title": "The Bell Beneath Ashford",
    "party_level": 3,
    "tone": "dark fantasy investigation",
    "public_hook": "A mining town has gone silent after the old chapel bell rang underground.",
    "dm_secret": "The bell is a planar anchor used by a trapped fiend."
  }
}
```

## 初步数据模型

```text
Campaign
  id
  title
  system
  tone
  party_level
  created_at

Character
  id
  campaign_id
  player_name
  character_name
  race
  class_name
  level
  stats
  skills
  hp
  ac
  inventory
  spells
  conditions

NPC
  id
  campaign_id
  name
  role
  public_description
  dm_secret
  attitude
  location_id

Location
  id
  campaign_id
  name
  public_description
  dm_notes
  connected_location_ids

Encounter
  id
  campaign_id
  title
  location_id
  enemies
  difficulty
  trigger
  reward

SessionEvent
  id
  campaign_id
  actor
  visibility
  content
  created_at
```

## 开发里程碑

### Milestone 1: 单机原型

- 创建战役
- 根据灵感生成 DND 短团模组
- 创建 2 到 4 张角色卡
- AI DM 文本主持
- 程序掷骰
- 自动保存 session log

### Milestone 2: 结构化战役工作台

- NPC 列表
- 地点列表
- 任务列表
- 线索列表
- DM 秘密与玩家可见信息分离
- AI 可检索资料库

### Milestone 3: 战斗辅助

- 先攻排序
- 回合管理
- 怪物行动建议
- HP/状态变化
- 简单战斗网格

### Milestone 4: 多人房间

- 玩家加入战役
- 多人聊天
- 角色权限
- 私密信息
- 暗骰
- WebSocket 实时同步

### Milestone 5: 内容生成增强

- 地图草图
- NPC 头像提示词
- 道具图提示词
- 随机遭遇表
- 城镇/地下城生成器
- 战役总结和下一章预告

## 第一版用户流程

1. 用户创建新战役
2. 选择 DND 5e 风格
3. 输入一句灵感
4. AI 生成短团模组
5. 用户编辑关键设定
6. 玩家创建角色卡
7. 点击“开始跑团”
8. AI DM 描述开场
9. 玩家输入行动
10. AI 判断是否需要检定
11. 程序掷骰
12. AI 根据结果叙事
13. 系统记录事件、状态、线索和任务进度

## 重要风险

- DND 官方规则和设定存在版权边界，需要避免复制官方受保护文本。
- AI 可能生成不平衡遭遇，需要加入 CR/等级/人数的校验。
- 长会话容易遗忘，需要结构化状态和摘要机制。
- 多人实时同步会增加复杂度，建议后置。
- AI DM 的自由发挥需要被工具和状态约束，否则容易跑偏。

## 暂定项目名称

候选名称：

- Arcane Table
- AI Dungeon Keeper
- QuestWeaver
- D20 Story Engine
- EmberDM

当前仓库暂用名称：`dnd-ai-assistant`

## 文档

- [Architecture](docs/architecture.md)
