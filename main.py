from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.star import Context, Star, register, StarTools
from astrbot.api import logger
import random
import shutil
from pathlib import Path


# 插件核心配置
PLUGIN_NAME = "astrbot_plugin_eatdrink"

@register(
    PLUGIN_NAME,
    "Cybercat",
    "随机推荐吃什么、喝什么，支持饮料分类推荐（如 /喝什么 奶茶）",
    "1.2.0",
    "https://github.com/Newbie-L/astrbot_plugin_eatdrink"
)
class RandomFoodDrinkPlugin(Star):
    DEFAULT_FOODS = [
        "火锅|火锅,川菜,重口",
        "烤肉|烧烤,肉食",
        "寿司|日料,生食",
        "麻辣烫|川菜,重口",
        "螺蛳粉|广西菜,重口",
        "牛肉面|面食,北方菜",
        "宫保鸡丁|川菜,家常菜",
        "鱼香肉丝|川菜,家常菜",
        "麻婆豆腐|川菜,家常菜",
        "饺子|面食,北方菜,家常菜",
        "面条|面食,北方菜",
        "米饭套餐|家常菜,主食"
    ]
    
    DEFAULT_DRINKS = [
        "芒果奶昔|奶茶", "珍珠奶绿|奶茶", "芋泥波波|奶茶,甜品",
        "拿铁咖啡|咖啡", "美式咖啡|咖啡", "生椰拿铁|咖啡",
        "柠檬气泡水|气泡水,果饮", "青提气泡水|气泡水",
        "酸梅汤|果饮", "鲜橙汁|果汁", "芒果汁|果汁",
        "绿茶|茶类", "红茶|茶类", "柠檬茶|茶类,果饮"
    ]

    DEFAULT_LIST_MAP = {
        "food.txt": DEFAULT_FOODS,
        "drink.txt": DEFAULT_DRINKS,
    }

    def __init__(self, context: Context):
        super().__init__(context) 
        
        # 1. 路径定义（框架规范目录）
        self.plugin_name = PLUGIN_NAME
        self.target_data_dir = Path(StarTools.get_data_dir(self.plugin_name))  # 插件数据目录
        self.plugin_root_dir = Path(__file__).parent  # 插件根目录
        self.template_dir = self.plugin_root_dir / "templates"  # 模板文件目录

        # 2. 自动复制模板文件（首次安装时）
        self._copy_template_files()

        # 3. 加载数据（食物列表 + 饮品列表+分类映射）
        self.food_list, self.food_category_map = self._load_food_with_category()
        self.drink_list, self.drink_category_map = self._load_drink_with_category()
        
        # 初始化日志（告知用户当前状态）
        logger.info(f"✅ 插件初始化完成，数据目录：{self.target_data_dir}")
        logger.info(f"📊 加载食物 {len(self.food_list)} 种，饮品 {len(self.drink_list)} 种")
        logger.info(f"📋 支持食物分类：{list(self.food_category_map.keys()) if self.food_category_map else '无'}") 
        logger.info(f"📋 支持饮品分类：{list(self.drink_category_map.keys()) if self.drink_category_map else '无'}")

    def _copy_template_files(self):
        self.target_data_dir.mkdir(parents=True, exist_ok=True)
        
        if not self.template_dir.exists():
            logger.warning(f"⚠️  未找到模板目录 {self.template_dir}，跳过自动复制")
            return

        for filename in ["food.txt", "drink.txt"]:
            template_file = self.template_dir / filename
            target_file = self.target_data_dir / filename
            
            if not target_file.exists() and template_file.exists():
                shutil.copy2(template_file, target_file)
                logger.info(f"📁 已自动创建 {target_file}（默认模板）")
            elif not template_file.exists():
                logger.warning(f"⚠️  模板文件 {template_file} 不存在，无法复制")

    def _load_food_with_category(self) -> tuple[list, dict]:
        file_path = self.target_data_dir / "food.txt"
        default_foods = self.DEFAULT_LIST_MAP.get("food.txt", [])
        
        food_list = [] 
        category_map = {} 

        if file_path.exists():
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    lines = [line.strip() for line in f.readlines() if line.strip()]
            except Exception as e:
                logger.error(f"❌ 读取 {file_path} 失败：{str(e)}，使用默认列表")
                lines = default_foods
        else:
            logger.warning(f"⚠️  文件 {file_path} 不存在，使用默认列表")
            lines = default_foods

        for line in lines:
            if "|" in line:
                food_name, categories_str = line.split("|", 1)
                food_name = food_name.strip()
                category_list = list(set([cat.strip() for cat in categories_str.split(",") if cat.strip()]))
            else:
                food_name = line.strip()
                category_list = []

            if food_name and food_name not in food_list:
                food_list.append(food_name)

            for cat in category_list:
                if cat not in category_map:
                    category_map[cat] = []
                if food_name not in category_map[cat]:
                    category_map[cat].append(food_name)

        return food_list, category_map

    def _load_drink_with_category(self) -> tuple[list, dict]:
        file_path = self.target_data_dir / "drink.txt"
        default_drinks = self.DEFAULT_LIST_MAP.get("drink.txt", [])
        
        drink_list = [] 
        category_map = {} 

        if file_path.exists():
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    lines = [line.strip() for line in f.readlines() if line.strip()]
            except Exception as e:
                logger.error(f"❌ 读取 {file_path} 失败：{str(e)}，使用默认列表")
                lines = default_drinks
        else:
            logger.warning(f"⚠️  文件 {file_path} 不存在，使用默认列表")
            lines = default_drinks

        for line in lines:
            if "|" in line:
                drink_name, categories_str = line.split("|", 1) 
                drink_name = drink_name.strip()
                category_list = list(set([cat.strip() for cat in categories_str.split(",") if cat.strip()]))
            else:
                drink_name = line.strip()
                category_list = []

            if drink_name and drink_name not in drink_list:
                drink_list.append(drink_name)

            for cat in category_list:
                if cat not in category_map:
                    category_map[cat] = []
                if drink_name not in category_map[cat]:
                    category_map[cat].append(drink_name)
        return drink_list, category_map

    @filter.command("吃什么", alias={"推荐吃的", "吃点啥"}, args=["event"])
    async def recommend_food(self, event: AstrMessageEvent):
        try:
            raw_msg = event.message_obj.message_str.strip()
        except AttributeError as e:
            logger.error(f"❌ 获取消息失败：{str(e)}")
            raw_msg = ""
        
        command_prefixes = ["吃什么", "推荐吃的", "吃点啥"]
        keyword = None

        for prefix in command_prefixes:
            if raw_msg.startswith(f"/{prefix}"):
                keyword = raw_msg[len(f"/{prefix}"):].strip()
                break

        if keyword:
            if keyword in self.food_category_map:
                recommended = random.choice(self.food_category_map[keyword])
                yield event.plain_result(f"🍚 分类推荐（{keyword}）：{recommended}")
                return
            
            matched_foods = [food for food in self.food_list if keyword in food]
            if matched_foods:
                recommended = random.choice(matched_foods)
                yield event.plain_result(f"🍚 符合“{keyword}”的推荐：{recommended}")
                return
            
            recommended = random.choice(self.food_list)
            yield event.plain_result(f"❌ 未找到“{keyword}”相关食物/分类，随机推荐：{recommended}")
            return

        recommended = random.choice(self.food_list)
        yield event.plain_result(f"🍚 随机推荐：{recommended}")

    @filter.command("喝什么", alias={"推荐喝的", "喝点啥"}, args=["event"])
    async def recommend_drink(self, event: AstrMessageEvent):
        try:
            raw_msg = event.message_obj.message_str.strip()
        except AttributeError as e:
            logger.error(f"❌ 获取消息失败：{str(e)}")
            raw_msg = ""
        
        command_prefixes = ["喝什么", "推荐喝的", "喝点啥"]
        keyword = None

        for prefix in command_prefixes:
            if raw_msg.startswith(f"/{prefix}"):
                keyword = raw_msg[len(f"/{prefix}"):].strip()
                break

        if keyword:
            if keyword in self.drink_category_map:
                recommended = random.choice(self.drink_category_map[keyword])
                yield event.plain_result(f"🥤 分类推荐（{keyword}）：{recommended}")
                return
            matched_drinks = [drink for drink in self.drink_list if keyword in drink]
            if matched_drinks:
                recommended = random.choice(matched_drinks)
                yield event.plain_result(f"🥤 符合“{keyword}”的推荐：{recommended}")
                return
            recommended = random.choice(self.drink_list)
            yield event.plain_result(f"❌ 未找到“{keyword}”相关饮品/分类，随机推荐：{recommended}")
            return
        recommended = random.choice(self.drink_list)
        yield event.plain_result(f"🥤 随机推荐：{recommended}")

    @filter.command("吃喝什么", args=["event"])
    async def recommend_food_drink(self, event: AstrMessageEvent):
        random_food = random.choice(self.food_list)
        random_drink = random.choice(self.drink_list)
        yield event.plain_result(
            f"🍽️  吃喝搭配推荐：\n"
            f"主食：{random_food}\n"
            f"饮品：{random_drink}"
        )

    async def terminate(self):
        logger.info("🔌 插件已卸载")


if __name__ == "__main__":
    logger.info("📱 吃喝推荐插件启动测试")