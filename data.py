import json
import os
import hashlib
import base64
from typing import Literal

from nonebot import get_driver
from nonebot.adapters.onebot.v11 import GroupMessageEvent, Message, MessageSegment
import mcstatus


from .config import Config
global_config = get_driver().config
plugin_config = Config.parse_obj(global_config)


class Server:
    """
    服务器类
    提供查询服务器状态,判断服务器在线状态是否改变等功能
    """

    def __init__(self, type: str, host: str, port: int, **argv):
        self.type = type.lower()
        self.host = host
        self.port = port
        assert self.type in ["java", "bedrock"]
        if self.type == "java":
            self.server = mcstatus.JavaServer(self.host, self.port)
        elif self.type == "bedrock":
            self.server = mcstatus.BedrockServer(self.host, self.port)

        self.last_online_status = None

    async def status(self):
        """
        获取服务器状态
        """
        try:
            return await self.server.async_status()
        except:
            return None

    async def get_online_status(self):
        """
        获取在线状态
        """
        if await self.status() is None:
            return "offline"
        else:
            return "online"

    async def is_online_status_changed(self):
        """
        在线状态是否改变
        """
        online_status = await self.get_online_status()
        if online_status != self.last_online_status and not self.last_online_status is None:
            self.last_online_status = online_status
            return online_status
        else:
            self.last_online_status = online_status
            return False

    # def get_format_dict(self):
    #     return {
    #         "server_name": self.name,
    #         "server_type": self.type,
    #         "server_host": self.host,
    #         "server_port": self.port,
    #     }

    # async def get_status_msg(self):
    #     """
    #     获取服务器消息
    #     """
    #     format_data = self.get_format_dict()
    #     server_status = await self.status()
    #     if not server_status is None:
    #         """
    #         所有服务器公有
    #         """
    #         format_data["server_latency"] = int(server_status.latency)
    #     else:
    #         """
    #         服务器离线
    #         """
    #         return Message.template(
    #             f"{plugin_config.format.server_title}\n"
    #             f"{plugin_config.format.server_offline}"
    #         ).format(**format_data)
    #     if self.type == "java" and not server_status is None:
    #         """
    #         JAVA服务器
    #         """
    #         assert isinstance(server_status, mcstatus.pinger.PingResponse)
    #         # 处理服务器图标
    #         server_favicon_data = base64.b64decode(server_status.favicon.split(",")[1])  # type: ignore
    #         format_data["server_favicon"] = MessageSegment.image(server_favicon_data)
    #         # 处理服务器版本
    #         format_data["server_version"] = server_status.version.name
    #         format_data["server_version_name"] = server_status.version.name
    #         format_data["server_version_protocol"] = server_status.version.protocol
    #         # 处理玩家数量
    #         format_data["server_players_max"] = server_status.players.max
    #         format_data["server_players_online"] = server_status.players.online
    #         return Message.template(
    #             f"{plugin_config.format.server_title}\n"
    #             f"{plugin_config.format.server_java_msg}"
    #         ).format(**format_data)
    #     elif self.type == "bedrock" and not server_status is None:
    #         """
    #         基岩服务器
    #         """
    #         assert isinstance(server_status, mcstatus.bedrock_status.BedrockStatusResponse)
    #         # 处理服务器版本
    #         format_data["server_version"] = server_status.version.brand + " " + server_status.version.version
    #         format_data["server_version_brand"] = server_status.version.brand
    #         format_data["server_version_protocol"] = server_status.version.protocol
    #         # 处理玩家数量
    #         format_data["server_players_max"] = server_status.players_max
    #         format_data["server_players_online"] = server_status.players_online

    #         return Message.template(
    #             f"{plugin_config.format.server_title}\n"
    #             f"{plugin_config.format.server_bedrock_msg}"
    #         ).format(**format_data)
    #     else:
    #         return Message.template(
    #             f"{plugin_config.format.server_title}\n"
    #             f"未知错误"
    #         ).format(**format_data)


class ServersMap:
    data = {
        "SERVER_HASH": {
            "bot_groups": {
                "BOT_GROUP_KEY": {
                    "data": {},
                }
            },
            "server": "Server(...)"
        }
    }

    def __init__(self, parent):
        self.parent = parent

    def load_data(self, config_data):
        self.data = {}
        for bot_id in config_data["bots"]:
            for group_id in config_data["bots"][bot_id]["groups"]:
                for server_data in config_data["bots"][bot_id]["groups"][group_id]["servers"]:
                    self.add_server(bot_id, group_id, server_data)

    def reload_data(self, config_data=data.copy()):
        self.data = {}
        self.load_data(config_data)

    def add_server(self, bot_id, group_id, server_data):
        # print(server_data)
        server_hash = hashlib.sha256(f"{server_data['host']}:{server_data['port']}".encode()).hexdigest()
        bot_group_key = f"{bot_id} {group_id}"
        if not server_hash in self.data:
            self.data[server_hash] = {
                "bot_groups": {},
                "server": Server(**server_data)
            }
            #
            #   {
            # ┃     "SERVER_HASH": {
            # ┃         "bot_groups":{
            #               "BOT_GROUP_HASH": {
            #                   ...data...
            #               }
            # ┃         },
            # ┃         "server": Server(...)
            # ┃     }
            #   }
            #

        if not bot_group_key in self.data[server_hash]["bot_groups"]:
            self.data[server_hash]["bot_groups"][bot_group_key] = {
                "enable": self.parent.get_group_data(bot_id, group_id)["enable"],
                "enable_query": self.parent.get_group_data(bot_id, group_id)["enable_query"],
                "enable_check": self.parent.get_group_data(bot_id, group_id)["enable_check"],
                **server_data
            }
            #
            #   {
            #       "SERVER_HASH": {
            #           "bot_groups":{
            # ┃             "BOT_GROUP_HASH": {
            # ┃                 ...data...
            # ┃             }
            #           },
            #           "server": Server(...)
            #       }
            #   }
            #
        return True

    def remove_group_server(self, bot_id, group_id, server_data):
        server_hash = hashlib.sha256(f"{server_data['host']}:{server_data['port']}".encode()).hexdigest()
        self.data[server_hash]["bot_groups"].pop(f"{bot_id} {group_id}")

    def get_server(self, server_hash: str):
        return {
            "hash": server_hash,
            **self.data[server_hash]
        }

    def get_bot_group_data(self, server_hash, bot_id, group_id):
        return self.get_server(server_hash)["bot_groups"][f"{bot_id} {group_id}"]

    def get_format_data(self, server_hash, bot_id, group_id):
        result = self.get_bot_group_data(server_hash, bot_id, group_id)
        return {
            "server_name": result["name"],
            "server_type": result["type"],
            "server_host": result["host"],
            "server_port": result["port"],
            "bot_id": bot_id,
            "group_id": group_id,
        }

    def create_server_message(self, server_hash, bot_id, group_id, server_status: mcstatus.pinger.PingResponse | mcstatus.bedrock_status.BedrockStatusResponse | None):
        """
        获取服务器消息
        """
        format_data = self.get_format_data(server_hash, bot_id, group_id)
        return self.format_server_message(server_status, format_data)

    def format_server_message(self, server_status: mcstatus.pinger.PingResponse | mcstatus.bedrock_status.BedrockStatusResponse | None, format_data: dict):
        if not server_status is None:
            """
            所有服务器公有
            """
            format_data["server_latency"] = int(server_status.latency)
        else:
            """
            服务器离线
            """
            return Message.template(
                f"{plugin_config.format.server_title}\n"
                f"{plugin_config.format.server_offline}"
            ).format(**format_data)
        if format_data["server_type"] == "java" and not server_status is None:
            """
            JAVA服务器
            """
            assert isinstance(server_status, mcstatus.pinger.PingResponse)
            # 处理服务器图标
            server_favicon_data = base64.b64decode(server_status.favicon.split(",")[1])  # type: ignore
            format_data["server_favicon"] = MessageSegment.image(server_favicon_data)
            # 处理服务器版本
            format_data["server_version"] = server_status.version.name
            format_data["server_version_name"] = server_status.version.name
            format_data["server_version_protocol"] = server_status.version.protocol
            # 处理玩家数量
            format_data["server_players_max"] = server_status.players.max
            format_data["server_players_online"] = server_status.players.online
            return Message.template(
                f"{plugin_config.format.server_title}\n"
                f"{plugin_config.format.server_java_msg}"
            ).format(**format_data)
        elif format_data["server_type"] == "bedrock" and not server_status is None:
            """
            基岩服务器
            """
            assert isinstance(server_status, mcstatus.bedrock_status.BedrockStatusResponse)
            # 处理服务器版本
            format_data["server_version"] = server_status.version.brand + " " + server_status.version.version
            format_data["server_version_brand"] = server_status.version.brand
            format_data["server_version_protocol"] = server_status.version.protocol
            # 处理玩家数量
            format_data["server_players_max"] = server_status.players_max
            format_data["server_players_online"] = server_status.players_online

            return Message.template(
                f"{plugin_config.format.server_title}\n"
                f"{plugin_config.format.server_bedrock_msg}"
            ).format(**format_data)
        else:
            return Message.template(
                f"{plugin_config.format.server_title}\n"
                f"未知错误"
            ).format(**format_data)


class Data:
    config_data = {
        "enable": True,
        "bots": {
            "BOT_ID": {
                "enable": True,
                "groups": {
                    "GROUP_ID": {
                        "enable": True,
                        "enable_query": True,
                        "enable_check": True,
                        "servers": [
                            {
                                "name": "服务器名称",
                                "addr": "服务器地址",
                                "port": "服务器端口",
                                "type": "服务器类型",

                            }
                        ]
                    }
                }
            }
        }
    }
    servers_map: ServersMap

    def __init__(self, path="./mcQuery"):
        self.servers_map = ServersMap(self)
        self.load_config_data(path)
        self.servers_map.load_data(self.config_data)

    def _init_folder(self, path):
        if not os.path.exists(path):
            os.mkdir(path)
        if not os.path.exists(f"{path}\\config_data.json"):
            with open(f"{path}\\config_data.json", "w", encoding="utf-8") as f:
                f.write("{}")

    def load_config_data(self, path="./mcQuery"):
        self.config_path = path
        self._init_folder(path)
        with open(f"{path}\\config_data.json", encoding="utf-8") as f:
            self.config_data = json.load(f)

    def reload_config_data(self):
        self.load_config_data(self.config_path)
        self.servers_map.reload_data(self.config_data)

    def save_config_data(self):
        with open(f"{self.config_path}\\config_data.json", "w", encoding="utf-8") as f:
            json.dump(self.config_data, f, indent=4, ensure_ascii=False)

    def get_bots(self):
        return self.config_data["bots"]

    def get_bot_data(self, bot_id):
        if not bot_id in self.config_data["bots"]:
            self.config_data["bots"][bot_id] = {
                "enable": False,
                "groups": {}
            }
        bot_data = self.config_data["bots"][bot_id]
        return {
            **bot_data,
            "enable": (self.config_data["enable"] and bot_data["enable"])
        }

    def get_group_data(self, bot_id, group_id) -> dict:
        if not group_id in self.config_data["bots"][bot_id]["groups"]:
            self.config_data["bots"][bot_id]["groups"][group_id] = {
                "enable": False,
                "enable_query": True,
                "enable_check": True,
                "servers": []
            
            }

        bot_data = self.get_bot_data(bot_id)
        group_data = bot_data["groups"][group_id]
        return {
            **group_data,
            "enable": (bot_data["enable"] and group_data["enable"])
        }

    #
    # get_group_data(bot_id, group_id)["enable"]
    #     ├─ group_data["enable"]
    #     └─ get_bot_data(bot_id)["enable"]
    #         ├─ bot_data["enable"]
    #         └─ config_data["enable"]
    #

    def add_server(self, bot_id, group_id, server_data: dict):
        assert (
            isinstance(server_data["name"], str) and
            isinstance(server_data["host"], str) and
            isinstance(server_data["port"], int) and
            isinstance(server_data["type"], str)
        )
        self.config_data["bots"][bot_id]["groups"][group_id]["servers"].append(server_data)
        self.servers_map.add_server(bot_id, group_id, server_data)
        self.save_config_data()

    def remove_server(self, bot_id, group_id, server_name) -> bool:
        server_data: dict
        for server_data in self.get_group_data(bot_id, group_id)["servers"]:
            if server_data["name"] == server_name:
                break
        else:
            # 没有名字相同的
            return False

        self.config_data["bots"][bot_id]["groups"][group_id]["servers"].remove(server_data)
        self.servers_map.remove_group_server(bot_id, group_id, server_data)
        self.save_config_data()
        return True
