# chat/models.py

from django.db import models
from django.contrib.auth.models import User

class UserProfile(models.Model):
    """Extends the built-in User model to track online status."""
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    is_online = models.BooleanField(default=False)
    
    def __str__(self):
        return f"{self.user.username} - {'Online' if self.is_online else 'Offline'}"


class Message(models.Model):
    """Stores each chat message between two users."""
    sender = models.ForeignKey(User, related_name='sent_messages', on_delete=models.CASCADE)
    receiver = models.ForeignKey(User, related_name='received_messages', on_delete=models.CASCADE)
    content = models.TextField()
    timestamp = models.DateTimeField(auto_now_add=True)  # Set automatically when created
    is_read = models.BooleanField(default=False)         # For unread message count
    
    class Meta:
        ordering = ['timestamp']  # Always show oldest messages first
    
    def __str__(self):
        return f"{self.sender.username} → {self.receiver.username}: {self.content[:30]}"
