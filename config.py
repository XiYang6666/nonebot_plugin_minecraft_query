from pydantic import BaseModel, Extra


class Config(BaseModel, extra=Extra.ignore):
    QueryInterval: int = 15

    class format:
        server_title = (
            "=== {server_name} ==="
        )
        server_java_msg = (
            "服务器ip: {server_host}:{server_port}\n"
            "服务器版本: {server_version}({server_type})\n"
            "在线人数: {server_players_online}/{server_players_max}\n"
            "ping: {server_latency}ms\n"
            "图标: {server_favicon}\n"
        )
        server_bedrock_msg = (
            "服务器ip: {server_host}:{server_port}\n"
            "服务器版本: {server_version}({server_type})\n"
            "在线人数: {server_players_online}/{server_players_max}\n"
            "ping: {server_latency}ms\n"
        )
        server_offline = (
            "服务器ip: {server_host}:{server_port}\n"
            "服务器离线\n"
        )

        server_state_change_online = (
            "服务器: {server_name}({server_host}:{server_port} {server_type}) 状态改变 离线=>在线"
        )

        server_state_change_offline = (
            "服务器: {server_name}({server_host}:{server_port} {server_type}) 状态改变 在线=>离线"
        )

        group_start_query = (
            "查询中..."
        )
        group_no_servers = (
            "群聊未添加服务器"
        )
        group_server_type_error = (
            "服务器类型错误,应当为\"java\"或\"bedrock\""
        )
        group_server_add_successful = (
            "服务器添加成功"
        )
        group_server_remove_successful = (
            "服务器移除成功"
        )
        group_server_remove_failed = (
            "服务器移除失败"
        )
        group_setting_success = (
            "配置更改成功"
        )
        group_setting_failed = (
            "配置更改失败"
        )
        group_setting_read_failed = (
            "配置读取失败"
        )
        group_insufficient_permissions = (
            "权限不足"
        )
        group_command_error = (
            "命令格式错误"
        )