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

@socketio.on('message')
def handle_message(data):
    room_code = data['room']
    message = data['message']
    username = data['username']
    send({'username': username, 'message': message}, to=room_code)
