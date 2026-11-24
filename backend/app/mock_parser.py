"""Small, deterministic Chinese parser for the explicitly labelled offline demo."""

import re
from datetime import date, timedelta

from .models import TaskDraft


WEEKDAYS = "一二三四五六日"
RELATIVE = {"今天": 0, "今日": 0, "今晚": 0, "今早": 0, "明天": 1, "明日": 1, "明晚": 1, "明早": 1, "后天": 2, "大后天": 3}
DAY = re.compile(
    r"(?P<iso>\d{4}-\d{2}-\d{2})|(?:(?P<year>\d{4})年)?(?P<month>\d{1,2})月(?P<day>\d{1,2})[日号]"
    r"|(?P<relative>大后天|今天|今日|今晚|今早|明天|明日|明晚|明早|后天)"
    r"|(?P<week>本|这|下)?(?:周|星期)(?P<weekday>[一二三四五六日天])"
)
PERIOD = r"凌晨|清晨|早晨|早上|上午|中午|下午|傍晚|晚上|晚间|今晚|明晚|今早|明早"
NUMBER = r"[0-9]{1,2}|[零一二两三四五六七八九十]{1,3}"
CLOCK = re.compile(
    rf"(?P<period>{PERIOD})?\s*(?:(?P<hour>{NUMBER})[点时](?:(?P<half>半)|(?P<minute>{NUMBER})分?)?"
    r"|(?P<iso_hour>[0-9]{1,2})[:：](?P<iso_minute>[0-9]{2}))(?![0-9])"
)
ACTIONS = (
    "写|做|交|提交|完成|背|发|阅读|读|看|复习|预习|整理|参加|安排|准备|买|购买|学习|练习|"
    "打扫|清理|打卡|打电话|联系|回复|打印|制作|录入|更新|修复|检查|修改|设计|实现|测试|"
    "预约|领取|取|寄|跑步|散步|运动|锻炼|洗|收拾|归还|还书|缴|交费|去|回|记|分析|"
    "统计|处理|下载|上传|翻译|报名|练|汇报|开会|上课|补|收集|讨论|面试|寄送"
)
ACTION = re.compile(rf"^(?:{ACTIONS})")
CLAUSE = re.compile(r"[，,。；;！!\n]+|(?:然后|接着|另外|还有|并且)|以及(?=(?:" + ACTIONS + r"))|[、并和](?=(?:" + ACTIONS + r"))")
PREFIX = re.compile(r"^(?:(?:请(?:帮我)?|帮我|提醒我|记得|记一下|我(?:打算|计划|准备|想要|想|要|需要)|需要|待办[：:]?|先|再|还要|还需|在|于|要|将于|之前|以前|前|有空(?:的时候|时)?|空的时候)\s*)+")
CATEGORY = {
    "英语学习": "六级|四级|单词|英语|雅思|托福|英文",
    "社会实践": "社会实践|社区实践|志愿|实践周记",
    "竞赛活动": "竞赛|比赛|数模|建模赛|挑战杯",
    "学生工作": "班会|学生会|班委|团支部|团日",
    "科学研究": "论文|文献|实验|课题|科研",
    "课程学习": "作业|课程|上课|预习|复习|考试|章节|课本",
    "日常生活": "买|做饭|运动|跑步|散步|吃饭|打扫|还书|洗|快递|购物|锻炼",
}


def resolve_date(match: re.Match[str], today: date) -> date:
    if match["iso"]:
        return date.fromisoformat(match["iso"])
    if match["month"]:
        return date(int(match["year"] or today.year), int(match["month"]), int(match["day"]))
    if match["relative"]:
        return today + timedelta(days=RELATIVE[match["relative"]])
    offset = WEEKDAYS.index(match["weekday"].replace("天", "日")) - today.weekday()
    if match["week"] == "下":
        offset += 7
    elif not match["week"]:
        offset %= 7
    return today + timedelta(days=offset)


def number(text: str) -> int:
    if text.isascii():
        return int(text)
    units = "零一二三四五六七八九"
    text = text.replace("两", "二")
    if "十" in text:
        tens, _, ones = text.partition("十")
        return (units.index(tens) if tens else 1) * 10 + (units.index(ones) if ones else 0)
    return int("".join(str(units.index(char)) for char in text))


def resolve_time(match: re.Match[str]) -> str | None:
    hour = number(match["hour"] or match["iso_hour"])
    minute = 30 if match["half"] else number(match["minute"] or match["iso_minute"] or "0")
    if match["period"] in ("下午", "傍晚", "晚上", "晚间", "今晚", "明晚") and 1 <= hour < 12:
        hour += 12
    if match["period"] == "中午" and hour in (1, 2):
        hour += 12
    if match["period"] == "凌晨" and hour == 12:
        hour = 0
    if hour >= 24 or minute >= 60:
        return None
    return f"{hour:02}:{minute:02}"


def parse_mock(raw: str, today: date) -> list[TaskDraft]:
    tasks = []
    for clause in CLAUSE.split(raw):
        text = clause.strip(" \t\r\n“”\"")
        if not text or re.search(r"[？?]|(?:吗|呢)$|不用|不需要|不要|无需|已经|不打算", text):
            continue
        day_match, clock_match = DAY.search(text), CLOCK.search(text)
        try:
            due_date = resolve_date(day_match, today) if day_match else None
            due_time = resolve_time(clock_match) if clock_match else None
        except (ValueError, OverflowError):
            # A malformed explicit deadline needs the user's attention in preview.
            due_date = due_time = None

        title = text
        for match in (clock_match, day_match):
            if match:
                title = title.replace(match[0], "", 1)
        title = re.sub(rf"(?:{PERIOD})|(?:优先级[为是：:]?[高中低]|[高中低]优先级|紧急|不着急)", "", title)
        title = PREFIX.sub("", title.strip()).strip(" ：:，,")
        if not ACTION.match(title):
            continue
        priority = "中"
        if re.search("高优先级|优先级[为是：:]?高|紧急", text):
            priority = "高"
        elif re.search("低优先级|优先级[为是：:]?低|不着急", text):
            priority = "低"
        category = next((c for c, pattern in CATEGORY.items() if re.search(pattern, title)), "其他")
        # Preserve implicit period, source deadline wording and other details for editing.
        tasks.append(TaskDraft(
            title=title, description=text if title != text else "", category=category, priority=priority,
            due_date=due_date.isoformat() if due_date else None, due_time=due_time,
        ))
    return tasks
