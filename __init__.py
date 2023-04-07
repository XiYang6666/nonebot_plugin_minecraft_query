import hashlib
import asyncio
import time
import json
import re

from nonebot import get_driver, get_bots, require, on_shell_command
from nonebot.params import ShellCommandArgs
from nonebot.permission import SUPERUSER
from nonebot.adapters.onebot.v11 import GroupMessageEvent, Message
from nonebot.internal.adapter.bot import Bot
from nonebot.rule import Namespace, ArgumentParser
from nonebot.log import logger
import mcstatus

from . import data

require("nonebot_plugin_apscheduler")
from nonebot_plugin_apscheduler import scheduler

from .config import Config
global_config = get_driver().config
plugin_config = Config.parse_obj(global_config)

servers_data = data.Data()


@scheduler.scheduled_job("interval", seconds=plugin_config.QueryInterval)
async def queryServerStatusChanged():
    """
    定时查询服务器状态是否改变
    状态改变则向群聊发送消息
    """

    # logger.debug(f"开始查询服务器在线状态")
    start_time = time.time()

    async def async_func_query(server: data.Server, server_hash: str):
        start_query_time = time.time()
        online_status_changed = await server.is_online_status_changed()
        if online_status_changed:
            if online_status_changed == "online":
                status_message = "离线=>在线"
                result[server_hash] = plugin_config.format.server_state_change_online
            else:
                status_message = "在线=>离线"
                result[server_hash] = plugin_config.format.server_state_change_offline
            logger.info(f"监测到服务器: {server.host}:{server.port}({server_hash}) 状态改变 {status_message}")

    tasks = []
    result = {}

    # 查询服务器状态
    for server_hash in servers_data.servers_map.data:
        server_data = servers_data.servers_map.get_server(server_hash)
        tasks.append(asyncio.create_task(async_func_query(server_data["server"], server_data["hash"])))

    if tasks:
        await asyncio.wait(tasks)

    # logger.debug(f"查询服务器状态完成,开始发送消息 耗时 {((time.time()-start_time)*1000):.0f}ms")

    # 发送消息
    tasks = []
    bots = get_bots()
    # logger.debug(f"bots:{bots} result:{result}")
    for server_hash in result:
        format_massage = result[server_hash]  # type: str
        for bot_group_key in servers_data.servers_map.get_server(server_hash)["bot_groups"]:
            bot_group_key: str
            bot_id, group_id = bot_group_key.split()
            bot_group_data = servers_data.servers_map.get_bot_group_data(server_hash, bot_id, group_id)

            if not (bot_group_data["enable"] and bot_group_data["enable_check"]):
                # 不允许检查状态,跳过
                continue
            if not bot_id in bots:
                # 机器人不存在,跳过
                continue

            message = format_massage.format(**servers_data.servers_map.get_format_data(server_hash, bot_id, group_id))
            tasks.append(asyncio.create_task(bots[bot_id].call_api("send_group_msg", group_id=group_id, message=message)))

    if tasks:
        await asyncio.wait(tasks)

    # logger.debug(f"查询服务器在线完成 共耗时 {((time.time()-start_time)*1000):.0f}ms")


parser = ArgumentParser("mc")
subparsers = parser.add_subparsers(dest="command_type")

# 查询
query = subparsers.add_parser("服务器", help="查询服务器")
query.add_argument("address")
query.add_argument("type", default="java")

# 列表
query_list = subparsers.add_parser("列表", help="查看列表")


# 管理命令
admin_parser = ArgumentParser("mc")
admin_subparsers = admin_parser.add_subparsers(dest="command_type")

# 添加
add = admin_subparsers.add_parser("添加", help="添加服务器")
add.add_argument("name")
add.add_argument("address")
add.add_argument("type", default="java")

# 移除
remove = admin_subparsers.add_parser("移除", help="移除服务器")
remove.add_argument("name")


# 设置
setting = admin_subparsers.add_parser("设置", help="设置群聊配置")
setting_subparsers = setting.add_subparsers(dest="mode")
setting_set = setting_subparsers.add_parser("设置")
setting_set.add_argument("key")
setting_set.add_argument("value")
setting_set = setting_subparsers.add_parser("读取")
setting_set.add_argument("key")


admin_command_query = on_shell_command("查询", parser=admin_parser, permission=SUPERUSER)


@admin_command_query.handle()
async def queryAllServersAdmin(bot: Bot, event: GroupMessageEvent, args: Namespace = ShellCommandArgs()):
    """
    群聊配置管理
    """
    global command_match_success
    command_match_success = True
    match args.command_type:
        case "添加":
            await add_server(bot, event, args.name, args.address, args.type)
        case "移除":
            await remove_server(bot, event, args.name)
        case "设置":
            if args.mode == "设置":
                await setting_group_set(bot, event, args.key, args.value)
            elif args.mode == "读取":
                await setting_group_get(bot, event, args.key)


command_query = on_shell_command("查询", parser=parser)
command_match_success: bool = False


@command_query.handle()
async def queryAllServers(bot: Bot, event: GroupMessageEvent, args: Namespace = ShellCommandArgs()):
    """
    查询群聊服务器状态
    """
    global command_match_success
    command_match_success = True
    match args.command_type:
        case None:
            # 查询
            await query_group(bot, event)
        case "服务器":
            await query_server(bot, event, args.address, args.type)
        case "列表":
            ...


@command_query.handle()
async def matchFailed(bot: Bot, event: GroupMessageEvent):
    global command_match_success
    if not command_match_success:
        await bot.send(event, plugin_config.format.group_command_error)
    command_match_success = False


async def query_group(bot: Bot, event: GroupMessageEvent):
    message = Message()
    bot_id = bot.self_id
    group_id = str(event.group_id)
    group_data = servers_data.get_group_data(bot_id, group_id)
    server_list = group_data["servers"]

    if not (group_data["enable"] and group_data["enable_query"]):
        # 不允许查询,退出
        return

    if not server_list:
        await bot.send(event, message=plugin_config.format.group_no_servers)
        return
    else:
        await bot.send(event, message=plugin_config.format.group_start_query)

    logger.info("开始查询群聊服务器")

    async def async_query_server(server: data.Server, server_hash: str):
        status = await server.status()
        result[server_hash] = status

    result = {}  # type: dict[str,mcstatus.pinger.PingResponse | mcstatus.bedrock_status.BedrockStatusResponse | None]
    tasks = []

    for server_data in server_list:
        server_hash = hashlib.sha256(f'{server_data["host"]}:{server_data["port"]}'.encode()).hexdigest()
        server = servers_data.servers_map.get_server(server_hash)["server"]  # type: data.Server
        tasks.append(asyncio.create_task(async_query_server(server, server_hash)))

    if tasks:
        await asyncio.wait(tasks)

    for server_data in server_list:
        server_hash = hashlib.sha256(f'{server_data["host"]}:{server_data["port"]}'.encode()).hexdigest()
        message += servers_data.servers_map.create_server_message(server_hash, bot.self_id, group_id, result[server_hash])
        message += ("" if server_data == server_list[-1] else "\n")

    await bot.send(event, message)


async def query_server(bot: Bot, event: GroupMessageEvent, address: str, server_type: str):
    host, port = address.split(":") + [(19132 if server_type.lower() == "bedrock" else 25565)]
    port = int(port)
    server = data.Server(server_type, host, port)  # type: ignore
    bot_id = bot.self_id
    group_id = str(event.group_id)
    format_data = {
        "server_name": "自定义查询",
        "server_type": server_type.lower(),
        "server_host": host,
        "server_port": port,
        "bot_id": bot_id,
        "group_id": group_id,
    }
    server_status = await server.status()
    await bot.send(event, servers_data.servers_map.format_server_message(server_status, format_data))


async def add_server(bot: Bot, event: GroupMessageEvent, name: str, address: str, server_type: str):
    if not server_type.lower() in ["java", "bedrock"]:
        await bot.send(event, plugin_config.format.group_server_type_error)
        return
    host, port = address.split(":") + ["19132" if server_type.lower() == "bedrock" else "25565"]
    port = int(port)
    servers_data.add_server(
        bot.self_id,
        str(event.group_id),
        {
            "name": name,
            "host": host,
            "port": port,
            "type": server_type
        }
    )
    await bot.send(event, plugin_config.format.group_server_add_successful)


async def remove_server(bot: Bot, event: GroupMessageEvent, name: str):
    if servers_data.remove_server(bot.self_id, str(event.group_id), name):
        await bot.send(event, plugin_config.format.group_server_remove_successful)
    else:
        await bot.send(event, plugin_config.format.group_server_remove_failed)


async def setting_group_set(bot: Bot, event: GroupMessageEvent, path: str, value):
    servers_data.get_group_data(bot.self_id, str(event.group_id))
    group_data = servers_data.config_data["bots"][bot.self_id]["groups"][str(event.group_id)]

    try:
        value = json.loads(value)
        temp = group_data
        key_list = path.split(".") if path != "." else []
        for i in range(len(key_list)):
            key = key_list[i]
            key = int(key) if re.match(r"^-?[0-9]*$", key) else key
            if i == (len(key_list) - 1):
                temp[key] = value
            else:
                temp = temp[key]
        servers_data.save_config_data()
    except KeyError:
        await bot.send(event, plugin_config.format.group_setting_failed.format(reason="KeyError"))
    except json.decoder.JSONDecodeError:
        await bot.send(event, plugin_config.format.group_setting_failed.format(reason="JSONDecodeError"))
    else:
        await bot.send(event, plugin_config.format.group_setting_success)


async def setting_group_get(bot: Bot, event: GroupMessageEvent, path: str):
    group_data = servers_data.get_group_data(bot.self_id, str(event.group_id))
    try:
        temp = group_data
        key_list = path.split(".") if path != "." else []
        for i in range(len(key_list)):
            key = key_list[i]
            key = int(key) if re.match(r"^-?[0-9]*$", key) else key
            temp = temp[key]
        
    except KeyError:
        await bot.send(event, plugin_config.format.group_setting_read_failed.format(reason="KeyError"))
    else:
        await bot.send(event, f"{type(temp).__name__.upper()} {json.dumps(temp,indent=4, ensure_ascii=False)}")
