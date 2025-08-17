from telethon.tl.types import ReactionEmoji, DialogFilter, TextWithEntities
from telethon.tl.functions.messages import SendReactionRequest, GetDialogFiltersRequest, UpdateDialogFilterRequest
from settings.logger import logger
from settings.config import config

async def send_reaction_to_message(client, chat_id, message_id, reaction):
    """
    Отправляет реакцию на сообщение (emoji).
    Args:
        client: Telegram client
        chat_id: ID чата
        message_id: ID сообщения
        reaction: строка-эмодзи, например '👍'
    """
    logger.debug(f'Sending reaction {reaction} to message {message_id} in chat {chat_id}')
    await client(SendReactionRequest(
        peer=chat_id,
        msg_id=message_id,
        reaction=[ReactionEmoji(emoticon=reaction)]
    ))
    logger.info(f'Reaction {reaction} sent to message {message_id} in chat {chat_id}')

async def forward_document_to_chat(client, sender, caption, document):
    try:
        text = f'ID: {sender.id} | Message from [{sender.first_name}](tg://user?id={sender.id})' + ('\n with caption: ' + caption if caption else '')
        target_chat = config.TECHNICAL_DATA.forwarding_chat
        await client.send_file(target_chat, file=document, caption=text)
        logger.info(f"Document forwarded to {target_chat} with link to sender {sender.id}")
    except Exception as e:
        logger.error(f"Failed to forward document from sender {sender.id} to {target_chat}: {e}", exc_info=True)

async def move_chat_to_folder_include_peers(client, user_id, folder_name):
    folders = await client(GetDialogFiltersRequest())
    existing_folder = next(
        (f for f in folders.filters if isinstance(f, DialogFilter) and getattr(f, 'title', None) and (
            (getattr(f.title, 'text', None) if hasattr(f.title, 'text') else f.title) == folder_name)),
        None
    )
    peer = await client.get_input_entity(user_id)
    if not existing_folder:
        used_ids = {f.id for f in folders.filters if hasattr(f, 'id')}
        for possible_id in range(2, 11):
            if possible_id not in used_ids:
                folder_id = possible_id
                break
        else:
            raise Exception("No available folder ID (2-10) for a new folder.")
        dialog_filter = DialogFilter(
            id=folder_id,
            title=TextWithEntities(
                text=folder_name,
                entities=[]
            ),
            pinned_peers=[],
            include_peers=[peer],
            exclude_peers=[],
            contacts=False,
            non_contacts=False,
            groups=False,
            broadcasts=False,
            bots=False
        )
        await client(UpdateDialogFilterRequest(id=folder_id, filter=dialog_filter))
    else:
        include_peers = list(getattr(existing_folder, 'include_peers', []))
        if peer not in include_peers:
            include_peers.append(peer)
            updated_filter = DialogFilter(
                id=existing_folder.id,
                title=existing_folder.title,
                pinned_peers=getattr(existing_folder, 'pinned_peers', []),
                include_peers=include_peers,
                exclude_peers=getattr(existing_folder, 'exclude_peers', []),
                contacts=getattr(existing_folder, 'contacts', False),
                non_contacts=getattr(existing_folder, 'non_contacts', False),
                groups=getattr(existing_folder, 'groups', False),
                broadcasts=getattr(existing_folder, 'broadcasts', False),
                bots=getattr(existing_folder, 'bots', False)
            )
            await client(UpdateDialogFilterRequest(id=existing_folder.id, filter=updated_filter)) 