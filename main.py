from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.star import Context, Star, register, StarTools  # 新增导入 StarTools
from astrbot.api import logger
import random
import os


@register(
    "astrbot_plugin_eatdrink", 
    "Cybercat",
    "随机推荐吃什么、喝什么，选择困难症救星～", 
    "1.2.0", 
    "https://github.com/Newbie-L/astrbot_plugin_eatdrink"
)
class RandomFoodDrinkPlugin(Star):
    def __init__(self, context: Context):
        super().__init__(context)
        self.data_dir = StarTools.get_data_dir("astrbot_plugin_eatdrink")
        os.makedirs(self.data_dir, exist_ok=True)

        self.food_list = self._load_list("food.txt")
        self.drink_list = self._load_list("drink.txt")
        
        logger.info("随机推荐插件初始化完成～")
        logger.info(f"数据目录：{self.data_dir}")
        logger.info(f"加载食物数量：{len(self.food_list)}，饮品数量：{len(self.drink_list)}")

    def _load_list(self, filename: str) -> list:
        """读取插件数据目录下的 txt 文件，返回列表（每行一个条目）"""
        file_path = os.path.join(self.data_dir, filename)
        default_list = []
        
        if filename == "food.txt":
            default_list = [
                "火锅", "烤肉", "寿司", "麻辣烫", "螺蛳粉", "牛肉面"
            ]
        elif filename == "drink.txt":
            default_list = [
                "奶茶", "咖啡", "可乐", "果汁", "柠檬水", "气泡水"
            ]
        
        try:
            # 读取文件内容（自动忽略空行和首尾空格）
            with open(file_path, "r", encoding="utf-8") as f:
                lines = [line.strip() for line in f.readlines() if line.strip()]
            return lines if lines else default_list
        except FileNotFoundError:
            logger.warning(f"未找到 {file_path}，将使用默认列表")
            return default_list
        except Exception as e:
            logger.error(f"读取 {file_path} 失败：{str(e)}，将使用默认列表")
            return default_list

    # 推荐吃的指令（逻辑不变）
    @filter.command("吃什么", alias={"推荐吃的", "吃点啥"})
    async def recommend_food(self, event: AstrMessageEvent):
        random_food = random.choice(self.food_list)
        logger.info(f"为用户 {event.get_sender_name()} 推荐美食：{random_food}")
        yield event.plain_result(f"🍚 推荐你吃：{random_food}")

    # 推荐喝的指令（逻辑不变）
    @filter.command("喝什么", alias={"推荐喝的", "喝点啥"})
    async def recommend_drink(self, event: AstrMessageEvent):
        random_drink = random.choice(self.drink_list)
        logger.info(f"为用户 {event.get_sender_name()} 推荐饮品：{random_drink}")
        yield event.plain_result(f"🥤 推荐你喝：{random_drink}")

    # 吃喝搭配推荐（逻辑不变）
    @filter.command("吃喝什么")
    async def recommend_food_drink(self, event: AstrMessageEvent):
        random_food = random.choice(self.food_list)
        random_drink = random.choice(self.drink_list)
        logger.info(f"为用户 {event.get_sender_name()} 推荐搭配：{random_food} + {random_drink}")
        yield event.plain_result(
            f"🍽️  吃喝搭配推荐：\n"
            f"主食：{random_food}\n"
            f"饮品：{random_drink}\n"
        )

    async def terminate(self):
        logger.info("随机推荐插件已卸载～")