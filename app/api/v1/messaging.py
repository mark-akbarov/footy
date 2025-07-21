from typing import List

from fastapi import APIRouter, HTTPException, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies.database import get_db_session
from api.dependencies.user import get_current_active_user
from db.crud.message import MessageCrud
from db.crud.user import UsersCrud
from db.tables.user import UserRole
from schemas.message import (
    CreateMessageSchema,
    UpdateMessageSchema,
    OutMessageSchema,
    MessageThreadSchema,
    PaginatedMessageSchema
)
from schemas.user import OutUserSchema


router = APIRouter(
    prefix="/messages",
    tags=["Messages"],
)


@router.post("", response_model=OutMessageSchema, status_code=status.HTTP_201_CREATED)
async def send_message(
    message_data: CreateMessageSchema,
    db: AsyncSession = Depends(get_db_session),
    current_user: OutUserSchema = Depends(get_current_active_user)
):
    """Send a message to another user."""
    message_crud = MessageCrud(db)
    user_crud = UsersCrud(db)
    
    # Check if receiver exists
    receiver = await user_crud.get_by_id(message_data.receiver_id)
    if not receiver:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Receiver not found"
        )
    
    # Don't allow sending messages to yourself
    if message_data.receiver_id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot send message to yourself"
        )
    
    # Create message
    message_dict = message_data.model_dump()
    message_dict["sender_id"] = current_user.id
    
    message = await message_crud.create(message_dict)
    await message_crud.commit_session()
    
    return OutMessageSchema.model_validate(message)


@router.get("/threads", response_model=List[MessageThreadSchema])
async def get_message_threads(
    db: AsyncSession = Depends(get_db_session),
    current_user: OutUserSchema = Depends(get_current_active_user)
):
    """Get message threads for current user."""
    message_crud = MessageCrud(db)
    threads = await message_crud.get_message_threads(current_user.id)
    
    return threads


@router.get("/conversation/{user_id}", response_model=List[OutMessageSchema])
async def get_conversation(
    user_id: int,
    db: AsyncSession = Depends(get_db_session),
    current_user: OutUserSchema = Depends(get_current_active_user)
):
    """Get conversation with a specific user."""
    message_crud = MessageCrud(db)
    user_crud = UsersCrud(db)
    
    # Check if the other user exists
    other_user = await user_crud.get_by_id(user_id)
    if not other_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # Get conversation
    messages = await message_crud.get_conversation(current_user.id, user_id)
    
    # Mark messages as read
    await message_crud.mark_conversation_as_read(current_user.id, user_id)
    
    return [OutMessageSchema.model_validate(msg) for msg in messages]


@router.get("/unread", response_model=List[OutMessageSchema])
async def get_unread_messages(
    db: AsyncSession = Depends(get_db_session),
    current_user: OutUserSchema = Depends(get_current_active_user)
):
    """Get all unread messages for current user."""
    message_crud = MessageCrud(db)
    messages = await message_crud.get_unread_messages(current_user.id)
    
    return [OutMessageSchema.model_validate(msg) for msg in messages]


@router.patch("/{message_id}/read", response_model=OutMessageSchema)
async def mark_message_as_read(
    message_id: int,
    db: AsyncSession = Depends(get_db_session),
    current_user: OutUserSchema = Depends(get_current_active_user)
):
    """Mark a message as read."""
    message_crud = MessageCrud(db)
    
    message = await message_crud.get_by_id(message_id)
    if not message:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Message not found"
        )
    
    # Only the receiver can mark a message as read
    if message.receiver_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only mark your own received messages as read"
        )
    
    updated_message = await message_crud.mark_as_read(message_id)
    
    return OutMessageSchema.model_validate(updated_message)


@router.get("/{message_id}", response_model=OutMessageSchema)
async def get_message(
    message_id: int,
    db: AsyncSession = Depends(get_db_session),
    current_user: OutUserSchema = Depends(get_current_active_user)
):
    """Get a specific message."""
    message_crud = MessageCrud(db)
    
    message = await message_crud.get_by_id(message_id)
    if not message:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Message not found"
        )
    
    # Only sender or receiver can view the message
    if message.sender_id != current_user.id and message.receiver_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have permission to view this message"
        )
    
    return OutMessageSchema.model_validate(message)


@router.post("/{message_id}/reply", response_model=OutMessageSchema)
async def reply_to_message(
    message_id: int,
    reply_content: CreateMessageSchema,
    db: AsyncSession = Depends(get_db_session),
    current_user: OutUserSchema = Depends(get_current_active_user)
):
    """Reply to a specific message."""
    message_crud = MessageCrud(db)
    
    # Get original message
    original_message = await message_crud.get_by_id(message_id)
    if not original_message:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Original message not found"
        )
    
    # Check if user has permission to reply
    if original_message.sender_id != current_user.id and original_message.receiver_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only reply to messages you are part of"
        )
    
    # Set receiver as the other participant
    if original_message.sender_id == current_user.id:
        receiver_id = original_message.receiver_id
    else:
        receiver_id = original_message.sender_id
    
    # Create reply
    reply_dict = reply_content.model_dump()
    reply_dict["sender_id"] = current_user.id
    reply_dict["receiver_id"] = receiver_id
    reply_dict["parent_message_id"] = message_id
    
    reply = await message_crud.create(reply_dict)
    await message_crud.commit_session()
    
    return OutMessageSchema.model_validate(reply)


@router.get("/{message_id}/replies", response_model=List[OutMessageSchema])
async def get_message_replies(
    message_id: int,
    db: AsyncSession = Depends(get_db_session),
    current_user: OutUserSchema = Depends(get_current_active_user)
):
    """Get all replies to a message."""
    message_crud = MessageCrud(db)
    
    # Check if original message exists and user has permission
    original_message = await message_crud.get_by_id(message_id)
    if not original_message:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Message not found"
        )
    
    if original_message.sender_id != current_user.id and original_message.receiver_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have permission to view replies to this message"
        )
    
    replies = await message_crud.get_replies_to_message(message_id)
    
    return [OutMessageSchema.model_validate(reply) for reply in replies] 