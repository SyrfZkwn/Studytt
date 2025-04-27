from flask import Blueprint, render_template
from flask_login import login_required, current_user
from flask_socketio import join_room, leave_room, send
from . import socketio
import random
from string import ascii_uppercase

chat = Blueprint('chat', __name__)

room = {}

def generate_unique_code(length):
    while True:
        code = ""
        for _ in range(length):
            code += random.choice(ascii_uppercase)
        if code not in room:
            break
    return code

@chat.route("/")
@login_required
def chat_view():
    return render_template("chat.html", user=current_user)

@socketio.on('join')
def handle_join(data):
    username = data['username']
    room_code = data['room']
    join_room(room_code)
    send(f"{username} has joined the room.", to=room_code)

@socketio.on('leave')
def handle_leave(data):
    username = data['username']
    room_code = data['room']
    leave_room(room_code)
    send(f"{username} has left the room.", to=room_code)

from .models import User, ChatMessage
from . import db
from flask_socketio import emit

@socketio.on('message')
def handle_message(data):
    room_code = data['room']
    message = data['message']
    username = data['username']

    # Save message to database
    sender = User.query.filter_by(username=username).first()
    # Extract receiver username from room_code
    users = room_code.split('_')
    receiver_username = users[0] if users[1] == username else users[1]
    receiver = User.query.filter_by(username=receiver_username).first()

    if sender and receiver:
        chat_message = ChatMessage(sender_id=sender.id, receiver_id=receiver.id, message=message)
        db.session.add(chat_message)
        db.session.commit()

    send({'username': username, 'message': message}, to=room_code)

@socketio.on('fetch_messages')
def fetch_messages(data):
    room_code = data['room']
    users = room_code.split('_')
    user1 = User.query.filter_by(username=users[0]).first()
    user2 = User.query.filter_by(username=users[1]).first()

    if not user1 or not user2:
        emit('message', 'Error: Users not found.')
        return

    # Fetch messages between the two users ordered by timestamp
    messages = ChatMessage.query.filter(
        ((ChatMessage.sender_id == user1.id) & (ChatMessage.receiver_id == user2.id)) |
        ((ChatMessage.sender_id == user2.id) & (ChatMessage.receiver_id == user1.id))
    ).order_by(ChatMessage.timestamp).all()

    for msg in messages:
        sender_user = user1 if msg.sender_id == user1.id else user2
        emit('message', {'username': sender_user.username, 'message': msg.message})
