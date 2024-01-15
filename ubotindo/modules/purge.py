import html, time
from typing import Optional, List

from telegram import Message, Chat, Update, Bot, User
from telegram.error import BadRequest
from telegram.ext import Filters
from telegram.utils.helpers import mention_html

from ubotindo import dispatcher, LOGGER
from ubotindo.modules.disable import DisableAbleCommandHandler
from ubotindo.modules.helper_funcs.chat_status import user_admin, can_delete
from ubotindo.modules.helper_funcs.admin_rights import user_can_delete
from ubotindo.modules.log_channel import loggable


@user_admin
@loggable
def purge(update, context):
    msg = update.effective_message  # type: Optional[Message]
    if msg.reply_to_message:
        user = update.effective_user  # type: Optional[User]
        chat = update.effective_chat  # type: Optional[Chat]
        if user_can_delete(chat, user, context.bot.id) == False:
           msg.reply_text("You don't have enough rights to delete message!")
           return ""
        args = context.args
        if can_delete(chat, context.bot.id):
            message_id = msg.reply_to_message.message_id
            delete_to = msg.message_id - 1
            if args and args[0].isdigit():
                new_del = message_id + int(args[0])
                # No point deleting messages which haven't been written yet.
                if new_del < delete_to:
                    delete_to = new_del

            for m_id in range(delete_to, message_id - 1, -1):  # Reverse iteration over message ids
                try:
                    context.bot.deleteMessage(chat.id, m_id)
                except BadRequest as err:
                    if err.message == "Message can't be deleted":
                        context.bot.send_message(chat.id, "Cannot delete all messages. The messages may be too old, I might "
                                                  "not have delete rights, or this might not be a supergroup.")

                    elif err.message != "Message to delete not found":
                        LOGGER.exception("Error while purging chat messages.")

            try:
                msg.delete()
            except BadRequest as err:
                if err.message == "Message can't be deleted":
                    context.bot.send_message(chat.id, "Cannot delete all messages. The messages may be too old, I might "
                                              "not have delete rights, or this might not be a supergroup.")

                elif err.message != "Message to delete not found":
                    LOGGER.exception("Error while purging chat messages.")

            del_msg = context.bot.send_message(chat.id, "Purge complete.")
            time.sleep(2)

            try:
                del_msg.delete()

            except BadRequest:
                pass

            return f"<b>{html.escape(chat.title)}:</b>\n#PURGE\n<b>Admin:</b> {mention_html(user.id, user.first_name)}\nPurged <code>{delete_to - message_id}</code> messages."

    else:
        msg.reply_text("Reply to a message to select where to start purging from.")

    return ""

    
@user_admin
@loggable
def del_message(update, context) -> str:
    if update.effective_message.reply_to_message:
        user = update.effective_user  # type: Optional[User]
        chat = update.effective_chat  # type: Optional[Chat]
        message = update.effective_message  # type: Optional[Message]
        if user_can_delete(chat, user, context.bot.id) == False:
           message.reply_text("You don't have enough rights to delete message!")
           return ""
        if can_delete(chat, context.bot.id):
            update.effective_message.reply_to_message.delete()
            update.effective_message.delete()
            return f"<b>{html.escape(chat.title)}:</b>\n#DEL\n<b>Admin:</b> {mention_html(user.id, user.first_name)}\nMessage deleted."
    else:
        update.effective_message.reply_text("Whadya want to delete?")

    return ""


__help__ = """
Deleting messages made easy with this command. Bot purges \
messages all together or individually.

*Admin only:*
 × /del: Deletes the message you replied to
 × /purge: Deletes all messages between this and the replied to message.
 × /purge <integer X>: Deletes the replied message, and X messages following it.
"""

__mod_name__ = "Purges"

DELETE_HANDLER = DisableAbleCommandHandler("del", del_message, filters=Filters.chat_type.groups, run_async=True)
PURGE_HANDLER = DisableAbleCommandHandler("purge", purge, filters=Filters.chat_type.groups, pass_args=True,  run_async=True)

dispatcher.add_handler(DELETE_HANDLER)
dispatcher.add_handler(PURGE_HANDLER)
