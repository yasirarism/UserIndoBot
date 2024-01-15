# UserindoBot
# Copyright (C) 2020  UserindoBot Team, <https://github.com/userbotindo/UserIndoBot.git>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import html
import re

import telegram
from telegram import (
    Chat,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
    ParseMode,
    User,
)
from telegram.error import BadRequest
from telegram.ext import (
    CallbackQueryHandler,
    CommandHandler,
    DispatcherHandlerStop,
    Filters,
    MessageHandler,
)
from telegram.utils.helpers import escape_markdown, mention_html

from ubotindo import dispatcher  # BAN_STICKER
from ubotindo.modules.connection import connected
from ubotindo.modules.disable import DisableAbleCommandHandler
from ubotindo.modules.helper_funcs.alternate import typing_action
from ubotindo.modules.helper_funcs.chat_status import (
    bot_admin,
    can_restrict,
    is_user_admin,
    user_admin,
    user_admin_no_reply,
)
from ubotindo.modules.helper_funcs.extraction import (
    extract_text,
    extract_user,
    extract_user_and_text,
)
from ubotindo.modules.helper_funcs.filters import CustomFilters
from ubotindo.modules.helper_funcs.misc import split_message
from ubotindo.modules.helper_funcs.string_handling import split_quotes
from ubotindo.modules.log_channel import loggable
from ubotindo.modules.sql import warns_sql as sql

WARN_HANDLER_GROUP = 9
CURRENT_WARNING_FILTER_STRING = (
    "<b>Current warning filters in this chat:</b>\n"
)


# Not async
def warn(
    user: User, chat: Chat, reason: str, message: Message, warner: User = None
) -> str:
    if is_user_admin(chat, user.id):
        message.reply_text("Damn admins, can't even be warned!")
        return ""

    if warner:
        warner_tag = mention_html(warner.id, warner.first_name)
    else:
        warner_tag = "Automated warn filter."

    limit, soft_warn = sql.get_warn_setting(chat.id)
    num_warns, reasons = sql.warn_user(user.id, chat.id, reason)
    if num_warns >= limit:
        sql.reset_warns(user.id, chat.id)
        if soft_warn:  # kick
            chat.unban_member(user.id)
            reply = f"That's {limit} warnings, {mention_html(user.id, user.first_name)} has been kicked!"

        else:  # ban
            chat.kick_member(user.id)
            reply = f"That's{limit} warnings, {mention_html(user.id, user.first_name)} has been banned!"

        for warn_reason in reasons:
            reply += f"\n - {html.escape(warn_reason)}"

        # message.bot.send_sticker(chat.id, BAN_STICKER)  # banhammer marie
        # sticker
        keyboard = None
        log_reason = f"<b>{html.escape(chat.title)}:</b>\n#WARN_BAN\n<b>Admin:</b> {warner_tag}\n<b>User:</b> {mention_html(user.id, user.first_name)} (<code>{user.id}</code>)\n<b>Reason:</b> {reason}\n<b>Counts:</b> <code>{num_warns}/{limit}</code>"

    else:
        keyboard = InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(
                        "Remove warn ⚠️", callback_data=f"rm_warn({user.id})"
                    )
                ]
            ]
        )

        reply = f"User {mention_html(user.id, user.first_name)} has {num_warns}/{limit} warnings... watch out!"
        if reason:
            reply += f"\nReason for last warn:\n{html.escape(reason)}"

        log_reason = f"<b>{html.escape(chat.title)}:</b>\n#WARN\n<b>Admin:</b> {warner_tag}\n<b>User:</b> {mention_html(user.id, user.first_name)} (<code>{user.id}</code>)\n<b>Reason:</b> {reason}\n<b>Counts:</b> <code>{num_warns}/{limit}</code>"

    try:
        message.reply_text(
            reply, reply_markup=keyboard, parse_mode=ParseMode.HTML
        )
    except BadRequest as excp:
        if excp.message == "Reply message not found":
            # Do not reply
            message.reply_text(
                reply,
                reply_markup=keyboard,
                parse_mode=ParseMode.HTML,
                quote=False,
            )
        else:
            raise
    return log_reason


@user_admin_no_reply
@bot_admin
@loggable
def button(update, context):
    query = update.callback_query
    user = update.effective_user
    if match := re.match(r"rm_warn\((.+?)\)", query.data):
        user_id = match.group(1)
        chat = update.effective_chat
        if res := sql.remove_warn(user_id, chat.id):
            update.effective_message.edit_text(
                f"Last warn removed by {mention_html(user.id, user.first_name)}.",
                parse_mode=ParseMode.HTML,
            )
            user_member = chat.get_member(user_id)
            return f"<b>{html.escape(chat.title)}:</b>\n#UNWARN\n<b>Admin:</b> {mention_html(user.id, user.first_name)}\n<b>User:</b> {mention_html(user_member.user.id, user_member.user.first_name)} (<code>{user_member.user.id}</code>)"
        else:
            update.effective_message.edit_text(
                "This user already has no warns.", parse_mode=ParseMode.HTML
            )

    return ""


@user_admin
@can_restrict
@loggable
@typing_action
def warn_user(update, context):
    message = update.effective_message
    chat = update.effective_chat
    warner = update.effective_user
    args = context.args
    user_id, reason = extract_user_and_text(message, args)

    if user_id:
        if (
            message.reply_to_message
            and message.reply_to_message.from_user.id == user_id
        ):
            return warn(
                message.reply_to_message.from_user,
                chat,
                reason,
                message.reply_to_message,
                warner,
            )
        else:
            return warn(
                chat.get_member(user_id).user, chat, reason, message, warner
            )
    else:
        message.reply_text("No user was designated!")
    return ""


@user_admin
@bot_admin
@loggable
@typing_action
def reset_warns(update, context):
    message = update.effective_message
    chat = update.effective_chat
    user = update.effective_user
    args = context.args
    if user_id := extract_user(message, args):
        sql.reset_warns(user_id, chat.id)
        message.reply_text("Warnings have been reset!")
        warned = chat.get_member(user_id).user
        return f"<b>{html.escape(chat.title)}:</b>\n#RESETWARNS\n<b>Admin:</b> {mention_html(user.id, user.first_name)}\n<b>User:</b> {mention_html(warned.id, warned.first_name)} (<code>{warned.id}</code>)"
    else:
        message.reply_text("No user has been designated!")
    return ""


@user_admin
@bot_admin
@loggable
@typing_action
def remove_warns(update, context):
    message = update.effective_message
    chat = update.effective_chat
    user = update.effective_user
    args = context.args
    if user_id := extract_user(message, args):
        sql.remove_warn(user_id, chat.id)
        message.reply_text("Last warn has been removed!")
        warned = chat.get_member(user_id).user
        return f"<b>{html.escape(chat.title)}:</b>\n#UNWARN\n<b>• Admin:</b> {mention_html(user.id, user.first_name)}\n<b>• User:</b> {mention_html(warned.id, warned.first_name)}\n<b>• ID:</b> <code>{warned.id}</code>"
    else:
        message.reply_text("No user has been designated!")
    return ""


@typing_action
def warns(update, context):
    message = update.effective_message
    chat = update.effective_chat
    args = context.args
    user = update.effective_user
    user_id = extract_user(message, args) or update.effective_user.id

    conn = connected(context.bot, update, chat, user.id, need_admin=False)
    if conn:
        chat_id = conn
        chat_name = dispatcher.bot.getChat(conn).title
    else:
        if chat.type == "private":
            return
        chat_id = update.effective_chat.id
        chat_name = chat.title

    result = sql.get_warns(user_id, chat_id)

    if result and result[0] != 0:
        num_warns, reasons = result
        limit, _ = sql.get_warn_setting(chat_id)

        if reasons:
            text = (
                f"This user has {num_warns}/{limit} warnings, in *{chat_name}* for the following reasons:"
                if conn
                else f"This user has {num_warns}/{limit} warnings, for the following reasons:"
            )
            for num, reason in enumerate(reasons, start=1):
                text += f"\n {num}. {reason}"
            msgs = split_message(text)
            for msg in msgs:
                update.effective_message.reply_text(msg, parse_mode="markdown")
        else:
            update.effective_message.reply_text(
                f"User has {num_warns}/{limit} warnings, but no reasons for any of them.",
                parse_mode="markdown",
            )
    else:
        update.effective_message.reply_text(
            "This user hasn't got any warnings!"
        )


# Dispatcher handler stop - do not async
@user_admin
def add_warn_filter(update, context):
    chat = update.effective_chat
    user = update.effective_user
    msg = update.effective_message
    args = msg.text.split(
        None, 1
    )  # use python's maxsplit to separate Cmd, keyword, and reply_text

    if conn := connected(context.bot, update, chat, user.id, need_admin=True):
        chat_id = conn
        chat_name = dispatcher.bot.getChat(conn).title
    else:
        if chat.type == "private":
            return
        chat_id = update.effective_chat.id
        chat_name = chat.title

    if len(args) < 2:
        return

    extracted = split_quotes(args[1])

    if len(extracted) < 2:
        return

    # set trigger -> lower, so as to avoid adding duplicate filters with
    # different cases
    keyword = extracted[0].lower()
    content = extracted[1]

    # Note: perhaps handlers can be removed somehow using sql.get_chat_filters
    for handler in dispatcher.handlers.get(WARN_HANDLER_GROUP, []):
        if handler.filters == (keyword, chat_id):
            dispatcher.remove_handler(handler, WARN_HANDLER_GROUP)

    sql.add_warn_filter(chat_id, keyword, content)

    update.effective_message.reply_text(
        f"Warn filter added for `{keyword}` in *{chat_name}*!",
        parse_mode="markdown",
    )
    raise DispatcherHandlerStop


@user_admin
def remove_warn_filter(update, context):
    chat = update.effective_chat
    user = update.effective_user
    msg = update.effective_message

    if conn := connected(context.bot, update, chat, user.id, need_admin=True):
        chat_id = conn
    elif chat.type == "private":
        return
    else:
        chat_id = update.effective_chat.id

    args = msg.text.split(
        None, 1
    )  # use python's maxsplit to separate Cmd, keyword, and reply_text

    if len(args) < 2:
        return

    extracted = split_quotes(args[1])

    if len(extracted) < 1:
        return

    to_remove = extracted[0]

    chat_filters = sql.get_chat_warn_triggers(chat_id)

    if not chat_filters:
        msg.reply_text("No warning filters are active here!")
        return

    for filt in chat_filters:
        if filt == to_remove:
            sql.remove_warn_filter(chat_id, to_remove)
            msg.reply_text("Yep, I'll stop warning people for that.")
            raise DispatcherHandlerStop

    msg.reply_text(
        "That's not a current warning filter - click: /warnlist for all active warning filters."
    )


def list_warn_filters(update, context):
    chat = update.effective_chat
    user = update.effective_user

    if conn := connected(context.bot, update, chat, user.id, need_admin=True):
        chat_id = conn
    elif chat.type == "private":
        return
    else:
        chat_id = update.effective_chat.id

    all_handlers = sql.get_chat_warn_triggers(chat_id)

    if not all_handlers:
        update.effective_message.reply_text(
            "No warning filters are active here!"
        )
        return

    filter_list = CURRENT_WARNING_FILTER_STRING
    for keyword in all_handlers:
        entry = f" - {html.escape(keyword)}\n"
        if len(entry) + len(filter_list) > telegram.MAX_MESSAGE_LENGTH:
            update.effective_message.reply_text(
                filter_list, parse_mode=ParseMode.HTML
            )
            filter_list = entry
        else:
            filter_list += entry

    if filter_list != CURRENT_WARNING_FILTER_STRING:
        update.effective_message.reply_text(
            filter_list, parse_mode=ParseMode.HTML
        )


@loggable
def reply_filter(update, context) -> str:
    chat = update.effective_chat
    message = update.effective_message

    chat_warn_filters = sql.get_chat_warn_triggers(chat.id)
    to_match = extract_text(message)
    if not to_match:
        return ""

    for keyword in chat_warn_filters:
        pattern = r"( |^|[^\w])" + re.escape(keyword) + r"( |$|[^\w])"
        if re.search(pattern, to_match, flags=re.IGNORECASE):
            user = update.effective_user
            warn_filter = sql.get_warn_filter(chat.id, keyword)
            return warn(user, chat, warn_filter.reply, message)
    return ""


@user_admin
@loggable
@typing_action
def set_warn_limit(update, context) -> str:
    chat = update.effective_chat
    user = update.effective_user
    msg = update.effective_message
    args = context.args

    if conn := connected(context.bot, update, chat, user.id, need_admin=True):
        chat_id = conn
        chat_name = dispatcher.bot.getChat(conn).title
    else:
        if chat.type == "private":
            return
        chat_id = update.effective_chat.id
        chat_name = chat.title

    if args:
        if args[0].isdigit():
            if int(args[0]) < 3:
                msg.reply_text("The minimum warn limit is 3!")
            else:
                sql.set_warn_limit(chat_id, int(args[0]))
                msg.reply_text(
                    f"Updated the warn limit to `{escape_markdown(args[0])}` in *{chat_name}*",
                    parse_mode="markdown",
                )
                return f"<b>{html.escape(chat_name)}:</b>\n#SET_WARN_LIMIT\n<b>Admin:</b> {mention_html(user.id, user.first_name)}\nSet the warn limit to <code>{args[0]}</code>"
        else:
            msg.reply_text("Give me a number as an arg!")
    else:
        limit, _ = sql.get_warn_setting(chat_id)

        msg.reply_text(f"The current warn in {chat_name} limit is {limit}")
    return ""


@user_admin
@typing_action
def set_warn_strength(update, context):
    chat = update.effective_chat
    user = update.effective_user
    msg = update.effective_message
    args = context.args

    if conn := connected(context.bot, update, chat, user.id, need_admin=True):
        chat_id = conn
        chat_name = dispatcher.bot.getChat(conn).title
    else:
        if chat.type == "private":
            return
        chat_id = update.effective_chat.id
        chat_name = chat.title

    if args:
        if args[0].lower() in ("on", "yes"):
            sql.set_warn_strength(chat_id, False)
            msg.reply_text("Too many warns will now result in a ban!")
            return f"<b>{chat_name}:</b>\n<b>Admin:</b> {mention_html(user.id, user.first_name)}\nHas enabled strong warns. Users will be banned."

        elif args[0].lower() in ("off", "no"):
            sql.set_warn_strength(chat_id, True)
            msg.reply_text(
                "Too many warns will now result in a kick! Users will be able to join again after."
            )
            return f"<b>{chat_name}:</b>\n<b>Admin:</b> {mention_html(user.id, user.first_name)}\nHas disabled strong warns. Users will only be kicked."

        else:
            msg.reply_text("I only understand on/yes/no/off!")
    else:
        _, soft_warn = sql.get_warn_setting(chat_id)
        if soft_warn:
            msg.reply_text(
                "Warns are currently set to *kick* users when they exceed the limits.",
                parse_mode=ParseMode.MARKDOWN,
            )
        else:
            msg.reply_text(
                "Warns are currently set to *ban* users when they exceed the limits.",
                parse_mode=ParseMode.MARKDOWN,
            )
    return ""


def __stats__():
    return f"× {sql.num_warns()} overall warns, across {sql.num_warn_chats()} chats.\n× {sql.num_warn_filters()} warn filters, across {sql.num_warn_filter_chats()} chats."


def __import_data__(chat_id, data):
    for user_id, count in data.get("warns", {}).items():
        for _ in range(int(count)):
            sql.warn_user(user_id, chat_id)


def __migrate__(old_chat_id, new_chat_id):
    sql.migrate_chat(old_chat_id, new_chat_id)


def __chat_settings__(chat_id, user_id):
    num_warn_filters = sql.num_warn_chat_filters(chat_id)
    limit, soft_warn = sql.get_warn_setting(chat_id)
    return f'This chat has `{num_warn_filters}` warn filters. It takes `{limit}` warns before the user gets *{"kicked" if soft_warn else "banned"}*.'


__help__ = """
 If you're looking for a way to automatically warn users when they say certain things, use the /addwarn command.
 An example of setting multiword warns filter:
 × `/addwarn "very angry" This is an angry user`
 This will automatically warn a user that triggers "very angry", with reason of 'This is an angry user'.
 An example of how to set a new multiword warning:
`/warn @user Because warning is fun`

 × /warns <userhandle>: Gets a user's number, and reason, of warnings.
 × /warnlist: Lists all current warning filters

*Admin only:*
 × /warn <userhandle>: Warns a user. After 3 warns, the user will be banned from the group. Can also be used as a reply.
 × /resetwarn <userhandle>: Resets the warnings for a user. Can also be used as a reply.
 × /rmwarn <userhandle>: Removes latest warn for a user. It also can be used as reply.
 × /unwarn <userhandle>: Same as /rmwarn
 × /addwarn <keyword> <reply message>: Sets a warning filter on a certain keyword. If you want your keyword to \
be a sentence, encompass it with quotes, as such: `/addwarn "very angry" This is an angry user`.
 × /nowarn <keyword>: Stops a warning filter
 × /warnlimit <num>: Sets the warning limit
 × /strongwarn <on/yes/off/no>: If set to on, exceeding the warn limit will result in a ban. Else, will just kick.
"""

__mod_name__ = "Warnings"

WARN_HANDLER = CommandHandler(
    "warn", warn_user, pass_args=True, filters=Filters.chat_type.groups, run_async=True
)
RESET_WARN_HANDLER = CommandHandler(
    ["resetwarn", "resetwarns"],
    reset_warns,
    pass_args=True,
    filters=Filters.chat_type.groups,
    run_async=True,
)
REMOVE_WARNS_HANDLER = CommandHandler(
    ["rmwarn", "unwarn"],
    remove_warns,
    pass_args=True,
    filters=Filters.chat_type.groups,
    run_async=True,
)
CALLBACK_QUERY_HANDLER = CallbackQueryHandler(button, pattern=r"rm_warn")
MYWARNS_HANDLER = DisableAbleCommandHandler(
    "warns", warns, pass_args=True, run_async=True
)
ADD_WARN_HANDLER = CommandHandler("addwarn", add_warn_filter, run_async=True)
RM_WARN_HANDLER = CommandHandler(
    ["nowarn", "stopwarn"], remove_warn_filter, run_async=True
)
LIST_WARN_HANDLER = DisableAbleCommandHandler(
    ["warnlist", "warnfilters"],
    list_warn_filters,
    admin_ok=True,
    run_async=True,
)
WARN_FILTER_HANDLER = MessageHandler(
    CustomFilters.has_text & Filters.chat_type.groups, reply_filter, run_async=True
)
WARN_LIMIT_HANDLER = CommandHandler(
    "warnlimit", set_warn_limit, pass_args=True, run_async=True
)
WARN_STRENGTH_HANDLER = CommandHandler(
    "strongwarn", set_warn_strength, pass_args=True, run_async=True
)

dispatcher.add_handler(WARN_HANDLER)
dispatcher.add_handler(CALLBACK_QUERY_HANDLER)
dispatcher.add_handler(RESET_WARN_HANDLER)
dispatcher.add_handler(REMOVE_WARNS_HANDLER)
dispatcher.add_handler(MYWARNS_HANDLER)
dispatcher.add_handler(ADD_WARN_HANDLER)
dispatcher.add_handler(RM_WARN_HANDLER)
dispatcher.add_handler(LIST_WARN_HANDLER)
dispatcher.add_handler(WARN_LIMIT_HANDLER)
dispatcher.add_handler(WARN_STRENGTH_HANDLER)
dispatcher.add_handler(WARN_FILTER_HANDLER, WARN_HANDLER_GROUP)
