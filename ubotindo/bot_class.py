# Copyright (C) 2020 - 2021 Divkix. All rights reserved. Source code available under the AGPL.
#
# This file is part of Alita_Robot.
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as
# published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version.

# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.

# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.


from platform import python_version
from threading import RLock
from time import gmtime, strftime, time

from pyrogram import Client, __version__
from pyrogram.raw.all import layer

from ubotindo import (
    API_HASH,
    APP_ID,
    TOKEN,
    LOGGER,
    MESSAGE_DUMP,
    NO_LOAD,
    UPTIME,
    WORKERS,
    get_self,
    load_cmds,
)
from ubotindo.database import MongoDB
from ubotindo.plugins import all_plugins
from ubotindo.tr_engine import lang_dict
from ubodindo.utils.kbhelpers import ikb

INITIAL_LOCK = RLock()

# Check if MESSAGE_DUMP is correct
if MESSAGE_DUMP == -100 or not str(MESSAGE_DUMP).startswith("-100"):
    raise Exception(
        "Please enter a vaild Supergroup ID, A Supergroup ID starts with -100",
    )


class YasirBot(Client):
    """Starts the Pyrogram Client on the Bot Token when we do 'python3 -m bot'"""

    def __init__(self):
        name = self.__class__.__name__.lower()

        super().__init__(
            "YasirBot",
            bot_token=TOKEN,
            plugins=dict(root=f"ubotindo.plugins", exclude=NO_LOAD),
            api_id=APP_ID,
            api_hash=API_HASH,
            workers=WORKERS,
        )

    async def start(self):
        """Start the bot."""
        await super().start()

        meh = await get_self(self)  # Get bot info from pyrogram client
        LOGGER.info("Starting bot...")

        # Load Languages
        lang_status = len(lang_dict) >= 1
        LOGGER.info(f"Loading Languages: {lang_status}\n")

        # Show in Log that bot has started
        LOGGER.info(
            f"Pyrogram v{__version__} (Layer - {layer}) started on {meh.username}",
        )
        LOGGER.info(f"Python Version: {python_version()}\n")

        # Get cmds and keys
        cmd_list = await load_cmds(await all_plugins())

        LOGGER.info(f"Plugins Loaded: {cmd_list}")
        LOGGER.info("Bot Started Successfully!\n")

    async def stop(self):
        await super().stop()
        MongoDB.close()
        LOGGER.info(
            f"""Bot Stopped.
        """,
        )
