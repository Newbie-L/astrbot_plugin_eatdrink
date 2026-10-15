"""吃喝什么呢？——随机推荐吃什么 / 喝什么的 AstrBot 插件。

数据来源：插件数据目录下的 ``food.txt`` / ``drink.txt``，首次运行时由 ``templates/``
自动复制生成。每行格式为 ``条目名|分类1,分类2``，分类部分可省略。

对外指令与回复文案保持与 1.2.2 完全一致，仅内部结构做了等价重构。
"""

from __future__ import annotations

import random
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from astrbot.api import logger
from astrbot.api.event import AstrMessageEvent, filter
from astrbot.api.star import Context, Star, StarTools, register

PLUGIN_NAME = "astrbot_plugin_eatdrink"
PLUGIN_VERSION = "1.3.0"
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

    def pick(self, keyword: str = "") -> tuple[str, str]:
        """挑选一条推荐，返回 ``(条目, 文案键)``。

        策略与原实现一致：精确分类 → 名称模糊匹配 → 兜底随机。
        """
        if keyword:
            bucket = self.category_map.get(keyword)
            if bucket:
                return random.choice(bucket), "category"
            fuzzy_matched = [item for item in self.items if keyword in item]
            if fuzzy_matched:
                return random.choice(fuzzy_matched), "fuzzy"
            return random.choice(self.items), "miss"
        return random.choice(self.items), "random"


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

        food = random.choice(self.catalogs[FOOD_SPEC.key].items)
        drink = random.choice(self.catalogs[DRINK_SPEC.key].items)
        yield event.plain_result(
            f"🍽️  吃喝搭配推荐：\n主食：{food}\n饮品：{drink}"
        )

    async def terminate(self):
        logger.info("🔌 插件已卸载")

    # -------------------------------------------------------------- 内部实现

    def _single_reply(self, event: AstrMessageEvent, spec: CatalogSpec):
        """按 ``spec`` 生成单条推荐回复。"""
        catalog = self.catalogs[spec.key]
        if not catalog.items:
            return event.plain_result(self._empty_hint(spec))

        keyword = _extract_keyword(_message_text(event), spec.command_names)
        item, message_key = catalog.pick(keyword)
        text = spec.messages[message_key].format(keyword=keyword, item=item)
        return event.plain_result(text)

    @staticmethod
    def _empty_hint(spec: CatalogSpec) -> str:
        return f"⚠️ 暂无可推荐的{spec.noun}，请检查数据文件 {spec.file_name}"
