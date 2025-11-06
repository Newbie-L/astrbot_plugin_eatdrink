from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.star import Context, Star, register
from astrbot.api import logger
import random

# 美食/饮品候选列表（可自行扩展）
FOOD_LIST = [
    "火锅", "烤肉", "寿司", "麻辣烫", "炸鸡", "螺蛳粉",
    "牛肉面", "披萨", "饺子", "汉堡", "盖浇饭", "酸菜鱼"
]
DRINK_LIST = [
    "奶茶", "咖啡", "可乐", "果汁", "柠檬水", "气泡水",
    "茶", "酸奶", "椰汁", "奶昔", "果茶", "苏打水"
]

@register(
    "astrbot_plugin_eat-drink", 
    "Cybercat",
    "随机推荐吃什么、喝什么，选择困难症救星～", 
    "1.0.0",
    "https://github.com/Newbie-L/astrbot_plugin_eat-drink"
)
class RandomFoodDrinkPlugin(Star):
    def __init__(self, context: Context):
        super().__init__(context)
        logger.info("随机推荐插件初始化完成～")

    # 推荐吃的指令
    @filter.command("吃什么", alias={"推荐吃的", "吃点啥"})
    async def recommend_food(self, event: AstrMessageEvent):
        '''发送 /吃什么 随机获取美食建议'''
        random_food = random.choice(FOOD_LIST)
        logger.info(f"为用户 {event.get_sender_name()} 推荐美食：{random_food}")
        yield event.plain_result(f"🍚 推荐你吃：{random_food}\n（发送 /吃什么 可重新随")

    # 推荐喝的指令
    @filter.command("喝什么", alias={"推荐喝的", "喝点啥"})
    async def recommend_drink(self, event: AstrMessageEvent):
        '''发送 /喝什么 随机获取饮品建议'''
        random_drink = random.choice(DRINK_LIST)
        logger.info(f"为用户 {event.get_sender_name()} 推荐饮品：{random_drink}")
        yield event.plain_result(f"🥤 推荐你喝：{random_drink}")

    # 合并指令（可选，支持 /推荐 吃的/喝的 格式）
    @filter.command("吃喝什么")
    async def recommend_food_drink(self, event: AstrMessageEvent):
        '''发送 吃喝什么 随机获取一组美食+饮品搭配'''
        random_food = random.choice(FOOD_LIST)
        random_drink = random.choice(DRINK_LIST)
        logger.info(f"为用户 {event.get_sender_name()} 推荐搭配：{random_food} + {random_drink}")
        yield event.plain_result(
            f"🍽️  吃喝搭配推荐：\n"
            f"主食：{random_food}\n"
            f"饮品：{random_drink}\n"
            f"（发送 吃喝什么 可重新随机搭配）"
        )

    async def terminate(self):
        '''插件卸载时执行'''
        logger.info("随机推荐插件已卸载～")