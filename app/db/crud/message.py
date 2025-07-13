from typing import Optional, List, Type

from sqlalchemy import select, and_, or_, func
from sqlalchemy.orm import selectinload, InstrumentedAttribute

from db.crud.base import BaseCrud
from db.tables.message import Message
from db.tables.user import User
from schemas.message import CreateMessageSchema, UpdateMessageSchema, MessageThreadSchema, OutMessageSchema, PaginatedMessageSchema


class MessageCrud(BaseCrud[CreateMessageSchema, UpdateMessageSchema, OutMessageSchema, PaginatedMessageSchema, Message]):
    @property
    def _table(self) -> Type[Message]:
        return Message

    @property
    def _out_schema(self) -> Type[OutMessageSchema]:
        return OutMessageSchema

    @property
    def default_ordering(self) -> InstrumentedAttribute:
        return self._table.created_at.desc()

    @property
    def _paginated_schema(self) -> Type[PaginatedMessageSchema]:
        return PaginatedMessageSchema
    async def get_messages_by_user_id(self, user_id: int) -> List[Message]:
        """Get all messages for a user (sent and received)."""
        query = select(Message).where(
            or_(
                Message.sender_id == user_id,
                Message.receiver_id == user_id
            )
        ).order_by(Message.created_at.desc())
        result = await self._db_session.execute(query)
        return result.scalars().all()

    async def get_conversation(self, user1_id: int, user2_id: int) -> List[Message]:
        """Get conversation between two users."""
        query = select(Message).where(
            or_(
                and_(Message.sender_id == user1_id, Message.receiver_id == user2_id),
                and_(Message.sender_id == user2_id, Message.receiver_id == user1_id)
            )
        ).order_by(Message.created_at.asc())
        result = await self._db_session.execute(query)
        return result.scalars().all()

    async def get_unread_messages(self, user_id: int) -> List[Message]:
        """Get all unread messages for a user."""
        query = select(Message).where(
            and_(
                Message.receiver_id == user_id,
                Message.is_read == False
            )
        ).order_by(Message.created_at.desc())
        result = await self._db_session.execute(query)
        return result.scalars().all()

    async def mark_as_read(self, message_id: int) -> Optional[Message]:
        """Mark a message as read."""
        message = await self.get_by_id(message_id)
        if message:
            message.is_read = True
            await self._db_session.commit()
            await self._db_session.refresh(message)
        return message

    async def mark_conversation_as_read(self, user_id: int, other_user_id: int) -> None:
        """Mark all messages in a conversation as read."""
        # This would need a direct update query for efficiency
        unread_messages = await self._db_session.execute(
            select(Message).where(
                and_(
                    Message.sender_id == other_user_id,
                    Message.receiver_id == user_id,
                    Message.is_read == False
                )
            )
        )
        for message in unread_messages.scalars().all():
            message.is_read = True
        await self._db_session.commit()

    async def get_message_threads(self, user_id: int) -> List[MessageThreadSchema]:
        """Get message threads for a user."""
        # This is a complex query that would need to be optimized
        # For now, we'll return a simple implementation
        query = select(Message).where(
            or_(
                Message.sender_id == user_id,
                Message.receiver_id == user_id
            )
        ).order_by(Message.created_at.desc())
        result = await self._db_session.execute(query)
        messages = result.scalars().all()
        
        # Group messages by conversation partner
        threads = {}
        for message in messages:
            partner_id = message.sender_id if message.receiver_id == user_id else message.receiver_id
            if partner_id not in threads:
                threads[partner_id] = {
                    'user_id': partner_id,
                    'last_message': message.content,
                    'last_message_time': message.created_at,
                    'unread_count': 0
                }
            if message.receiver_id == user_id and not message.is_read:
                threads[partner_id]['unread_count'] += 1
        
        return list(threads.values())

    async def get_replies_to_message(self, message_id: int) -> List[Message]:
        """Get all replies to a message."""
        query = select(Message).where(Message.parent_message_id == message_id).order_by(Message.created_at.asc())
        result = await self._db_session.execute(query)
        return result.scalars().all() 