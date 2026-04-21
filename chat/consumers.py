# chat/consumers.py

import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.contrib.auth.models import User
from .models import Message, UserProfile


class ChatConsumer(AsyncWebsocketConsumer):

    async def connect(self):
        """Called when a WebSocket connection is opened."""
        self.user = self.scope['user']

        # Reject if not logged in
        if not self.user.is_authenticated:
            await self.close()
            return

        self.other_user_id = self.scope['url_route']['kwargs']['user_id']

        # Unique room name — sort IDs so both users share the same room
        user_ids = sorted([self.user.id, int(self.other_user_id)])
        self.room_group_name = f"chat_{user_ids[0]}_{user_ids[1]}"

        # Join the room group
        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )

        # Mark user as online in DB
        await self.set_online_status(True)

        # Accept the WebSocket connection
        await self.accept()

        # Tell the other user this person is now online
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'user_status',
                'user_id': self.user.id,
                'is_online': True,
            }
        )

    async def disconnect(self, close_code):
        """Called when WebSocket closes."""
        # Only clean up if connect() completed successfully
        if not hasattr(self, 'room_group_name'):
            return

        await self.set_online_status(False)

        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'user_status',
                'user_id': self.user.id,
                'is_online': False,
            }
        )

        await self.channel_layer.group_discard(
            self.room_group_name,
            self.channel_name
        )

    async def receive(self, text_data):
        """Called when a message arrives from the browser."""
        try:
            data = json.loads(text_data)
        except json.JSONDecodeError:
            return

        message_type = data.get('type', 'message')

        if message_type == 'typing':
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    'type': 'typing_indicator',
                    'user_id': self.user.id,
                    'username': self.user.username,
                    'is_typing': data.get('is_typing', False),
                }
            )

        elif message_type == 'message':
            message_content = data.get('message', '').strip()
            if not message_content:
                return

            # Save to DB and broadcast
            message = await self.save_message(message_content)

            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    'type': 'chat_message',
                    'message': message_content,
                    'sender_id': self.user.id,
                    'sender_username': self.user.username,
                    'timestamp': message.timestamp.strftime('%H:%M'),
                    'message_id': message.id,
                }
            )

    # ---- Handlers called by group_send ----

    async def chat_message(self, event):
        """Forward a chat message to the browser."""
        await self.send(text_data=json.dumps({
            'type': 'message',
            'message': event['message'],
            'sender_id': event['sender_id'],
            'sender_username': event['sender_username'],
            'timestamp': event['timestamp'],
            'message_id': event['message_id'],
        }))

    async def typing_indicator(self, event):
        """Forward typing status — but not back to the typer."""
        if event['user_id'] != self.user.id:
            await self.send(text_data=json.dumps({
                'type': 'typing',
                'username': event['username'],
                'is_typing': event['is_typing'],
            }))

    async def user_status(self, event):
        """Forward online/offline status to the browser."""
        await self.send(text_data=json.dumps({
            'type': 'status',
            'user_id': event['user_id'],
            'is_online': event['is_online'],
        }))

    # ---- DB helpers (must be async-wrapped) ----

    @database_sync_to_async
    def save_message(self, content):
        other_user = User.objects.get(id=self.other_user_id)
        return Message.objects.create(
            sender=self.user,
            receiver=other_user,
            content=content,
        )

    @database_sync_to_async
    def set_online_status(self, status):
        profile, _ = UserProfile.objects.get_or_create(user=self.user)
        profile.is_online = status
        profile.save()