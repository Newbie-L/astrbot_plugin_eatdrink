from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.star import Context, Star, register
from astrbot.api import logger
import random


FOOD_LIST = [
    # 中餐家常菜
    "宫保鸡丁", "鱼香肉丝", "麻婆豆腐", "回锅肉", "番茄炒蛋", "清炒时蔬",
    "红烧肉", "糖醋排骨", "可乐鸡翅", "水煮鱼", "酸菜鱼", "剁椒鱼头",
    # 特色小吃/地方菜
    "火锅", "烤肉", "寿司", "麻辣烫", "螺蛳粉", "牛肉面", "饺子", "馄饨",
    "肠粉", "热干面", "炸酱面", "油泼面", "刀削面", "过桥米线", "桂林米粉",
    "章鱼小丸子", "烤冷面", "手抓饼", "煎饼果子", "肉夹馍", "驴肉火烧",
    # 西餐/快餐
    "披萨", "汉堡", "炸鸡", "薯条", "牛排", "意大利面", "三明治", "沙拉",
    # 其他品类
    "盖浇饭", "煲仔饭", "卤肉饭", "蛋炒饭", "炒河粉", "炒米粉", "砂锅", "冒菜"
]


DRINK_LIST = [
    # 奶茶/奶饮
    "珍珠奶茶", "波霸奶茶", "芋圆奶茶", "奶盖茶", "杨枝甘露", "烧仙草",
    "生椰拿铁", "厚乳拿铁", "芋泥波波奶绿", "草莓奶盖", "芒果奶昔", "奥利奥奶茶",
    # 咖啡类
    "美式咖啡", "拿铁咖啡", "卡布奇诺", "摩卡咖啡", "冷萃咖啡", "冰滴咖啡",
    # 纯茶/花果茶
    "茉莉花茶", "乌龙茶", "普洱茶", "红茶", "绿茶", "柠檬茶", "百香果茶",
    "玫瑰茶", "菊花茶", "金银花茶", "大麦茶", "冬瓜茶",
    # 碳酸/气泡类
    "可乐", "雪碧", "芬达", "气泡水", "苏打水", "柠檬气泡水", "荔枝气泡饮",
    # 果汁/天然饮品
    "橙汁", "苹果汁", "芒果汁", "葡萄汁", "西瓜汁", "猕猴桃汁", "酸梅汤",
    "椰汁", "芦荟汁", "山楂汁", "蜂蜜水", "酸奶", "乳酸菌饮料"
]

@register(
    "astrbot_plugin_eat-drink", 
    "Cybercat",
    "随机推荐吃什么、喝什么，选择困难症救星～", 
    "1.0.1",
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
        yield event.plain_result(f"🍚 推荐你吃：{random_food}")

    # 推荐喝的指令
    @filter.command("喝什么", alias={"推荐喝的", "喝点啥"})
    async def recommend_drink(self, event: AstrMessageEvent):
        '''发送 /喝什么 随机获取饮品建议'''
        random_drink = random.choice(DRINK_LIST)
        logger.info(f"为用户 {event.get_sender_name()} 推荐饮品：{random_drink}")
        yield event.plain_result(f"🥤 推荐你喝：{random_drink}")

    # 合并指令（可选，支持 /吃喝什么 格式）
    @filter.command("吃喝什么")
    async def recommend_food_drink(self, event: AstrMessageEvent):
        '''发送 /吃喝什么 随机获取一组美食+饮品搭配'''
        random_food = random.choice(FOOD_LIST)
        random_drink = random.choice(DRINK_LIST)
        logger.info(f"为用户 {event.get_sender_name()} 推荐搭配：{random_food} + {random_drink}")
        yield event.plain_result(
            f"🍽️  吃喝搭配推荐：\n"
            f"主食：{random_food}\n"
            f"饮品：{random_drink}\n"
        )

    async def terminate(self):
        '''插件卸载时执行'''
        logger.info("随机推荐插件已卸载～")