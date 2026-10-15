"""吃喝什么呢？——随机推荐吃什么 / 喝什么的 AstrBot 插件。

数据来源：插件数据目录下的 ``food.txt`` / ``drink.txt``，首次运行时由 ``templates/``
自动复制生成。每行格式为 ``条目名|分类1,分类2``，分类部分可省略。

1.4.0 起：根据当前时间自动切换推荐策略——
- 早餐时段优先 早餐 分类；
- 正餐时段全量随机；
- 深夜时段偏清淡、并附带温和提醒。
"""

from __future__ import annotations

import random
import shutil
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable

from astrbot.api import logger
from astrbot.api.event import AstrMessageEvent, filter
from astrbot.api.star import Context, Star, StarTools, register

PLUGIN_NAME = "astrbot_plugin_eatdrink"
PLUGIN_VERSION = "1.4.0"
PLUGIN_REPO = "https://github.com/Newbie-L/astrbot_plugin_eatdrink"

# 正常情况下 AstrBot 的 WakingCheckStage 已经剥离唤醒前缀，这里只做兜底，
# 兼容直接阅读原始消息（message_obj.message_str）的场景。
_WAKE_PREFIX_CHARS = "/#!！.。·"


def _split_categories(raw: str) -> list[str]:
    """拆分 ``火锅,川菜`` 形式的分类串：去空、去重、保持书写顺序。"""
    parts = (part.strip() for part in raw.split(","))
    return [part for part in dict.fromkeys(parts) if part]


def _parse_catalog_lines(lines: Iterable[str]) -> tuple[list[str], dict[str, list[str]]]:
    """把数据行解析为 ``(条目列表, {分类: [条目, ...]})``。"""
    items: list[str] = []
    category_map: dict[str, list[str]] = {}

    for line in lines:
        name, _, categories = line.partition("|")
        name = name.strip()
        if not name:
            continue
        if name not in items:
            items.append(name)
        for category in _split_categories(categories):
            bucket = category_map.setdefault(category, [])
            if name not in bucket:
                bucket.append(name)

    return items, category_map


def _extract_keyword(raw_text: str, command_names: tuple[str, ...]) -> str:
    """取出指令之后的关键词，例如 ``/吃什么 川菜`` -> ``川菜``。

    ``command_names`` 必须按长度降序传入，否则 ``吃什么`` 会抢先截断 ``吃喝什么``。
    """
    text = raw_text.strip()
    if text and text[0] in _WAKE_PREFIX_CHARS:
        text = text.lstrip(_WAKE_PREFIX_CHARS).strip()
    for name in command_names:
        if text.startswith(name):
            return text[len(name) :].strip()
    # 兜底：指令必然位于首个 token，丢弃它，剩余内容视为关键词
    _, _, rest = text.partition(" ")
    return rest.strip()


def _message_text(event: AstrMessageEvent) -> str:
    """获取消息纯文本，优先使用框架已剥离唤醒前缀的 ``message_str``。"""
    text = getattr(event, "message_str", "")
    if isinstance(text, str) and text.strip():
        return text
    raw = getattr(getattr(event, "message_obj", None), "message_str", "")
    return raw if isinstance(raw, str) else ""


# ---------------------------------------------------------------- 时段配置


@dataclass(frozen=True)
class MealSlot:
    """一段时段的推荐偏好与附加提示。

    小时窗口支持跨午夜：当 ``hours_end < hours_start`` 时视为 ``[hours_start, 24) ∪ [0, hours_end)``，
    例如 ``(22, 5)`` 即 22:00–次日 04:59。

    - ``preferred_categories`` 为空 ⇒ 该时段不限制池子（用全量随机）。
    - ``gentle_reminder`` 非空 ⇒ 选完条目后追加到文案尾部。
    """

    name: str
    label: str
    preferred_categories: frozenset[str] = frozenset()
    gentle_reminder: str | None = None
    hours_start: int = 0
    hours_end: int = 24


# 默认时段表。边界值用「小时」粒度，不绑定日期；测试可通过 ``datetime`` 注入。
# 默认顺序也是兜底优先级（首个匹配的胜出）。
MEAL_SLOTS: tuple[MealSlot, ...] = (
    MealSlot(
        name="breakfast",
        label="🌅 早餐时段",
        preferred_categories=frozenset({"早餐"}),
        hours_start=5,
        hours_end=10,
    ),
    MealSlot(
        name="meal",
        label="🍱 正餐时段",
        hours_start=10,
        hours_end=22,
    ),
    MealSlot(
        name="late_night",
        label="🌙 深夜时段",
        # 跨夜窗口 22:00 → 次日 04:59。「过了十二点用户还问」也命中这里。
        preferred_categories=frozenset({"清淡", "汤品"}),
        gentle_reminder="温馨提示：夜深啦，少吃一点、清淡一点更健康哦~",
        hours_start=22,
        hours_end=5,
    ),
)


def _in_window(hour: int, start: int, end: int) -> bool:
    """判断 ``hour`` 是否落在 ``[start, end)`` 窗口内；``start > end`` 时视为跨夜。"""
    if start <= end:
        return start <= hour < end
    return hour >= start or hour < end


def current_meal_slot(now: datetime | None = None) -> MealSlot:
    """根据当前小时数确定所处时段；未匹配时回落到正餐（不限制池）。

    接受可选 ``now`` 参数便于单元测试注入固定时刻；缺省取 ``datetime.now()``。
    """
    hour = (now or datetime.now()).hour
    for slot in MEAL_SLOTS:
        if _in_window(hour, slot.hours_start, slot.hours_end):
            return slot
    # 理论不会走到这里：MEAL_SLOTS 拼起来覆盖 [0, 24)，但兜底用正餐。
    return next(slot for slot in MEAL_SLOTS if slot.name == "meal")


@dataclass(frozen=True)
class CatalogSpec:
    """一类推荐条目的静态描述：命令、数据文件、兜底列表与回复文案。"""

    key: str
    command: str
    aliases: frozenset[str]
    file_name: str
    fallback: tuple[str, ...]
    noun: str
    messages: dict[str, str]

    @property
    def command_names(self) -> tuple[str, ...]:
        """指令名与别名，按长度降序，供关键词提取使用。"""
        return tuple(sorted((self.command, *self.aliases), key=len, reverse=True))


FOOD_SPEC = CatalogSpec(
    key="food",
    command="吃什么",
    aliases=frozenset({"推荐吃的", "吃点啥"}),
    file_name="food.txt",
    fallback=(
        "火锅|火锅,川菜,重口", "烤肉|烧烤,肉食", "寿司|日料,生食",
        "麻辣烫|川菜,重口", "螺蛳粉|广西菜,重口", "牛肉面|面食,北方菜",
        "宫保鸡丁|川菜,家常菜", "鱼香肉丝|川菜,家常菜", "麻婆豆腐|川菜,家常菜",
        "饺子|面食,北方菜,家常菜", "面条|面食,北方菜", "米饭套餐|家常菜,主食",
    ),
    noun="食物",
    messages={
        "category": "🍚 分类推荐（{keyword}）：{item}",
        "fuzzy": "🍚 符合“{keyword}”的推荐：{item}",
        "miss": "❌ 未找到“{keyword}”相关食物/分类，随机推荐：{item}",
        "random": "🍚 随机推荐：{item}",
        "late_night_random": "🌙 深夜推荐：{item}",
    },
)

DRINK_SPEC = CatalogSpec(
    key="drink",
    command="喝什么",
    aliases=frozenset({"推荐喝的", "喝点啥"}),
    file_name="drink.txt",
    fallback=(
        "芒果奶昔|奶茶", "珍珠奶绿|奶茶", "芋泥波波|奶茶,甜品",
        "拿铁咖啡|咖啡", "美式咖啡|咖啡", "生椰拿铁|咖啡",
        "柠檬气泡水|气泡水,果饮", "青提气泡水|气泡水",
        "酸梅汤|果饮", "鲜橙汁|果汁", "芒果汁|果汁",
        "绿茶|茶类", "红茶|茶类", "柠檬茶|茶类,果饮",
    ),
    noun="饮品",
    messages={
        "category": "🥤 分类推荐（{keyword}）：{item}",
        "fuzzy": "🥤 符合“{keyword}”的推荐：{item}",
        "miss": "❌ 未找到“{keyword}”相关饮品/分类，随机推荐：{item}",
        "random": "🥤 随机推荐：{item}",
        "late_night_random": "🌙 深夜推荐：{item}",
    },
)

CATALOG_SPECS: tuple[CatalogSpec, ...] = (FOOD_SPEC, DRINK_SPEC)


class Catalog:
    """单类条目的内存索引：数据文件准备、解析，以及三级挑选策略。"""

    def __init__(self, spec: CatalogSpec, data_dir: Path, template_dir: Path) -> None:
        self.spec = spec
        self.data_file = data_dir / spec.file_name
        self.template_file = template_dir / spec.file_name
        self.items: list[str] = []
        self.category_map: dict[str, list[str]] = {}
        # 每个条目对应的分类集合（去重、空集合表示条目无分类），
        # 供 ``pick`` 在无关键词时段偏好场景下过滤池子。
        self._item_categories: list[tuple[str, frozenset[str]]] = []

    def prepare(self) -> None:
        """确保数据文件存在（不存在则复制模板），随后解析条目。"""
        self.data_file.parent.mkdir(parents=True, exist_ok=True)
        self._copy_template()
        self._load()

    def _copy_template(self) -> None:
        if self.data_file.exists():
            return
        if not self.template_file.exists():
            logger.warning(
                f"⚠️  模板文件 {self.template_file} 不存在，将使用内置兜底列表"
            )
            return
        shutil.copy2(self.template_file, self.data_file)
        logger.info(f"📁 已自动创建 {self.data_file}（默认模板）")

    def _load(self) -> None:
        lines: Iterable[str]
        if self.data_file.exists():
            try:
                with open(self.data_file, encoding="utf-8") as file:
                    lines = [line.strip() for line in file if line.strip()]
            except (OSError, UnicodeDecodeError) as exc:
                logger.error(
                    f"❌ 读取 {self.data_file} 失败：{exc}，使用内置兜底列表"
                )
                lines = self.spec.fallback
        else:
            logger.warning(f"⚠️  文件 {self.data_file} 不存在，使用内置兜底列表")
            lines = self.spec.fallback

        self.items, self.category_map = _parse_catalog_lines(lines)
        # 重建条目→分类的反向索引：遍历分类字典，把分类名拼到每个条目上。
        item_to_cats: dict[str, set[str]] = {item: set() for item in self.items}
        for category, bucket in self.category_map.items():
            for item in bucket:
                item_to_cats.setdefault(item, set()).add(category)
        self._item_categories = [
            (item, frozenset(cats)) for item, cats in item_to_cats.items()
        ]

    def pick(
        self, keyword: str = "", *, slot: MealSlot | None = None
    ) -> tuple[str, str]:
        """挑选一条推荐，返回 ``(条目, 文案键)``。

        策略与原实现一致：精确分类 → 名称模糊匹配 → 兜底随机；
        时段有偏好分类时，无关键词场景下优先从偏好池抽，无匹配再退回全量。

        文案键 ``late_night_random`` 固定在「深夜时段且无关键词」时返回，
        调用方拿到后拼接温和提醒。偏好池命中与否都共用此键——避免
        抽到「清单淡汤」条目却仍走 ``random`` 文案让用户看不出是深夜。
        """
        if keyword:
            bucket = self.category_map.get(keyword)
            if bucket:
                return random.choice(bucket), "category"
            fuzzy_matched = [item for item in self.items if keyword in item]
            if fuzzy_matched:
                return random.choice(fuzzy_matched), "fuzzy"
            return random.choice(self.items), "miss"

        pool = self.items
        if slot and slot.preferred_categories:
            biased_pool = [
                item
                for item, cats in self._item_categories
                if cats & slot.preferred_categories
            ]
            if biased_pool:
                pool = biased_pool

        if slot is not None and slot.gentle_reminder is not None:
            return random.choice(pool), "late_night_random"
        return random.choice(pool), "random"


@register(
    PLUGIN_NAME,
    "Cybercat",
    "随机推荐吃什么、喝什么的插件",
    PLUGIN_VERSION,
    PLUGIN_REPO,
)
class RandomFoodDrinkPlugin(Star):
    """随机推荐吃喝的插件。"""

    def __init__(self, context: Context):
        super().__init__(context)

        self.data_dir = Path(StarTools.get_data_dir(PLUGIN_NAME))
        self.template_dir = Path(__file__).parent / "templates"

        self.catalogs: dict[str, Catalog] = {}
        for spec in CATALOG_SPECS:
            catalog = Catalog(spec, self.data_dir, self.template_dir)
            catalog.prepare()
            self.catalogs[spec.key] = catalog
            logger.info(
                f"📊 已加载{spec.noun} {len(catalog.items)} 种，"
                f"分类 {len(catalog.category_map)} 个：{list(catalog.category_map)}"
            )

        logger.info(f"✅ 插件初始化完成，数据目录：{self.data_dir}")

    # ------------------------------------------------------------------ 指令

    @filter.command("吃什么", alias={"推荐吃的", "吃点啥"})
    async def recommend_food(self, event: AstrMessageEvent):
        """随机推荐吃什么，可跟分类或菜名，例如 /吃什么 川菜"""
        yield self._single_reply(event, FOOD_SPEC)

    @filter.command("喝什么", alias={"推荐喝的", "喝点啥"})
    async def recommend_drink(self, event: AstrMessageEvent):
        """随机推荐喝什么，可跟分类或饮品名，例如 /喝什么 奶茶"""
        yield self._single_reply(event, DRINK_SPEC)

    @filter.command("吃喝什么")
    async def recommend_food_drink(self, event: AstrMessageEvent):
        """随机推荐一餐吃喝搭配"""
        empty_spec = next(
            (spec for spec in CATALOG_SPECS if not self.catalogs[spec.key].items),
            None,
        )
        if empty_spec is not None:
            yield event.plain_result(self._empty_hint(empty_spec))
            return

        slot = current_meal_slot()
        food, _ = self.catalogs[FOOD_SPEC.key].pick(slot=slot)
        drink, _ = self.catalogs[DRINK_SPEC.key].pick(slot=slot)
        lines = [
            "🍽️  吃喝搭配推荐：",
            f"主食：{food}",
            f"饮品：{drink}",
        ]
        # 深夜时段统一追加温和提醒；搭配场景也覆盖。
        if slot.gentle_reminder:
            lines.append(slot.gentle_reminder)
        yield event.plain_result("\n".join(lines))

    async def terminate(self):
        logger.info("🔌 插件已卸载")

    # -------------------------------------------------------------- 内部实现

    def _single_reply(self, event: AstrMessageEvent, spec: CatalogSpec):
        """按 ``spec`` 生成单条推荐回复。

        时段策略：
        - 关键词命中分类 / 名称：走原有逻辑，时段不影响（用户明确表达优先）。
        - 无关键词：先按 ``current_meal_slot()`` 的偏好池抽取，匹配不上退回全量。
        - 深夜时段无关键词：回复末尾追加温和提醒。
        """
        catalog = self.catalogs[spec.key]
        if not catalog.items:
            return event.plain_result(self._empty_hint(spec))

        slot = current_meal_slot()
        keyword = _extract_keyword(_message_text(event), spec.command_names)
        item, message_key = catalog.pick(keyword, slot=slot)
        text = spec.messages[message_key].format(keyword=keyword, item=item)
        # 深夜无关键词：无论池子是否命中，都追加温和提醒。
        if not keyword and slot.gentle_reminder:
            text = f"{text}\n{slot.gentle_reminder}"
        return event.plain_result(text)

    @staticmethod
    def _empty_hint(spec: CatalogSpec) -> str:
        return f"⚠️ 暂无可推荐的{spec.noun}，请检查数据文件 {spec.file_name}"
