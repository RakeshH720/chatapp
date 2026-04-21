# chat/views.py

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.models import User
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from django.db.models import Q
from .models import Message, UserProfile


def signup_view(request):
    """Handle user registration."""
    if request.method == 'POST':
        form = UserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            # Create a UserProfile for the new user
            UserProfile.objects.create(user=user)
            login(request, user)
            return redirect('home')
    else:
        form = UserCreationForm()
    return render(request, 'chat/signup.html', {'form': form})


def login_view(request):
    """Handle user login."""
    if request.method == 'POST':
        form = AuthenticationForm(data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            return redirect('home')
    else:
        form = AuthenticationForm()
    return render(request, 'chat/login.html', {'form': form})


def logout_view(request):
    """Handle user logout — also marks them offline."""
    if request.user.is_authenticated:
        try:
            profile = UserProfile.objects.get(user=request.user)
            profile.is_online = False
            profile.save()
        except UserProfile.DoesNotExist:
            pass
    logout(request)
    return redirect('login')


@login_required
def home_view(request):
    """Show list of all users to chat with, with unread message counts."""
    # Get all users except the logged-in user
    users = User.objects.exclude(id=request.user.id)
    
    # Build user list with online status and unread count
    user_data = []
    for user in users:
        # Ensure each user has a profile
        profile, _ = UserProfile.objects.get_or_create(user=user)
        
        # Count unread messages from this user
        unread_count = Message.objects.filter(
            sender=user,
            receiver=request.user,
            is_read=False
        ).count()
        
        user_data.append({
            'user': user,
            'is_online': profile.is_online,
            'unread_count': unread_count,
        })
    
    return render(request, 'chat/home.html', {'user_data': user_data})


@login_required
def chat_room_view(request, user_id):
    """Show the chat room between current user and another user."""
    other_user = get_object_or_404(User, id=user_id)
    
    # Get message history between these two users
    messages = Message.objects.filter(
        Q(sender=request.user, receiver=other_user) |
        Q(sender=other_user, receiver=request.user)
    ).order_by('timestamp')
    
    # Mark messages from other user as read
    Message.objects.filter(
        sender=other_user,
        receiver=request.user,
        is_read=False
    ).update(is_read=True)
    
    # Get online status of the other user
    other_profile, _ = UserProfile.objects.get_or_create(user=other_user)
    
    return render(request, 'chat/chat_room.html', {
        'other_user': other_user,
        'messages': messages,
        'is_online': other_profile.is_online,
    })
