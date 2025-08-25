from pathlib import Path
from typing import Dict, Any
from logging import Logger
from discord.ext import commands
from traitlets import Complex
from settings.DefaultTypes.number import NumberSetting
from settings.DefaultTypes.arr import ArraySetting
from settings.DefaultTypes.complex import ComplexSetting
from settings.DefaultTypes.role import RoleSetting
from settings.DefaultTypes.boolean import BooleanSetting
from discord import Embed
from utils.InteractionView import InteractionView

async def dynamic_update_fn1(value: Dict[str, Any], view: InteractionView) -> Embed:
    language = await view.client.translator.get_language(guild_id=view.interaction.guild.id)
    translate_module = view.client.translator.get_translator_sync(language=language, module_name="XPSystem")

    role = value["role"] if "role" in value.keys() else None
    mul = value["multiplier"] if "multiplier" in value.keys() else None
    return Embed(
        title=translate_module("settings.xp_multiplier.embed_title"),
        description=f"{translate_module('settings.xp_multiplier.embed_description')}\n\n"
        f"{translate_module('settings.xp_multiplier.role.name')}: **{role if role else translate_module(f'settings.xp_multiplier.role.description')}**\n"
        f"{translate_module('settings.xp_multiplier.multiplier.name')}: **{mul if mul else translate_module('settings.xp_multiplier.multiplier.description')}**",
        color=0x00FF00,
    )

async def dynamic_update_fn2(value: Dict[str, Any], view: InteractionView) -> Embed:
    language = await view.client.translator.get_language(guild_id=view.interaction.guild.id)
    translate_module = view.client.translator.get_translator_sync(language=language, module_name="XPSystem")

    xp = value["xp"] if "xp" in value.keys() else None
    role = value["role"] if "role" in value.keys() else None

    return Embed(
        title=translate_module("settings.role_by_xp.embed_title"),
        description=f"{translate_module('settings.role_by_xp.embed_description')}\n\n"
        f":fire: **{xp} XP** → **{role if role else translate_module('settings.role_by_xp.role.description')}**",
        color=0x00FF00,
    )

async def dynamic_update_fn3(value: Dict[str, Any], view: InteractionView) -> Embed:
    language = await view.client.translator.get_language(guild_id=view.interaction.guild.id)
    translate_module = view.client.translator.get_translator_sync(language=language, module_name="XPSystem")

    xp_roles = value.get("role_xp_list", [])
    remove_previous_role = value.get("remove_previous_role", False)

    role_list = ""
    for entry in xp_roles:
        xp = entry.get("xp_required", None)
        role = entry.get("assigned_role", translate_module("settings.role_by_xp.role.description"))
        role_list += f":fire: **{xp} XP** → **{role}**\n"

    return Embed(
        title=translate_module("settings.role_by_xp.embed_title"),
        description=f"{translate_module('settings.role_by_xp.embed_description')}\n\n"
        f"{role_list}\n"
        f"{translate_module('settings.role_by_xp.remove_previous_status')}: **{translate_module('common.enabled') if remove_previous_role else translate_module('common.disabled')}**",
        color=0x00FF00,
    )


def setup(bot: commands.Bot, logger: Logger):
    """
    Initializes the XPSystem module.
    """

    xp_multiplier_setting = ArraySetting(
        name="settings.xp_multiplier.name",
        description="settings.xp_multiplier.description",
        id="xp_multiplier",
        locales=True,
        module_name="XPSystem",
        child=ComplexSetting(
            name="settings.xp_multiplier.role_multiplier.name",
            description="settings.xp_multiplier.role_multiplier.description",
            id="role_multiplier",
            schema={
                "role": RoleSetting(
                    name="settings.xp_multiplier.role.name",
                    description="settings.xp_multiplier.role.description",
                    id="role",
                ),
                "multiplier": NumberSetting(
                    name="settings.xp_multiplier.multiplier.name",
                    description="settings.xp_multiplier.multiplier.description",
                    id="multiplier",
                    value=1,
                    minValue=0.1,
                    maxValue=10,
                ),
            },
            update_fn=dynamic_update_fn1,
        ),
    )

    remove_previous_role = BooleanSetting(
        name="settings.role_by_xp.remove_previous.name",
        description="settings.role_by_xp.remove_previous.description",
        id="role_by_xp_remove_previous",
        value=False,
        locales=True,
        module_name="XPSystem",
    )

    role_by_xp_setting = ComplexSetting(
        name="settings.role_by_xp.name",
        description="settings.role_by_xp.description",
        locales=True,
        module_name="XPSystem",
        id="role_by_xp",
        schema={
            "role_xp_list": ArraySetting(
                name="settings.role_by_xp.role_xp_list.name",
                description="settings.role_by_xp.role_xp_list.description",
                id="role_by_xp_list",
                locales=True,
                module_name="XPSystem",
                child=ComplexSetting(
                    name="settings.role_by_xp.role_xp.name",
                    description="settings.role_by_xp.role_xp.description",
                    id="role_by_xp_entry",
                    schema={
                        "xp_required": NumberSetting(
                            name="settings.role_by_xp.role_xp.xp_required.name",
                            description="settings.role_by_xp.role_xp.xp_required.description",
                            id="role_by_xp_xp_required",
                            value=1000,
                            minValue=1,
                            maxValue=9999999999999,
                        ),
                        "assigned_role": RoleSetting(
                            name="settings.role_by_xp.role_xp.assigned_role.name",
                            description="settings.role_by_xp.role_xp.assigned_role.description",
                            id="role_by_xp_assigned_role",
                        ),
                    },
                    update_fn=dynamic_update_fn2,
                ),
            ),
            "remove_previous_role": remove_previous_role,
        },
        update_fn=dynamic_update_fn3,
    )


    settings = [xp_multiplier_setting, role_by_xp_setting]
    interface = {}

    return {"interface": interface, "settings": settings, "user": {}}
