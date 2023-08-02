import json
from channels.generic.websocket import WebsocketConsumer, SyncConsumer
from asgiref.sync import async_to_sync
from channels.exceptions import (
    StopConsumer,
    AcceptConnection,
    DenyConnection,
    InvalidChannelLayerError,
)
from channels.db import database_sync_to_async
from scribbleapp.serializers import RoomSerializer
from .models import Player, Room
from random_word import RandomWords
import random
from .mock import words


class DrawingConsumer(WebsocketConsumer):
    consumer_id = None

    def connect(self):
        self.accept()

    # def websocket_connect(self, message):
    #     return self.accept()
    # async_to_sync(self.channel_layer.group_add)("drawing", self.channel_name)

    def disconnect(self, close_code):
        # Get the player associated with this channel_name
        player = self.get_player_by_channel_name(self.channel_name)
        if player:
            room = self.get_room_by_player(player)
            if room:
                # Remove the player from the room
                room.players.remove(player)

                # Check if there are no other players in the room
                if room.players.count() == 0:
                    # If no players left in the room, delete the room
                    room.delete()
                else:
                    # Save the room if there are still players in it
                    room.save()

                # Delete the player
                player.delete()

    @database_sync_to_async
    def get_player_by_channel_name(self, channel_name):
        try:
            return Player.objects.get(channel_name=channel_name)
        except Player.DoesNotExist:
            return None

    @database_sync_to_async
    def get_room_by_player(self, player):
        try:
            return Room.objects.get(players=player)
        except Room.DoesNotExist:
            return None

    def check_and_change_turn(self, room_name):
        try:
            room = Room.objects.get(name=room_name)
            idx = room.turnIndex
            if room.turnIndex + 1 == room.players.count():
                room.currentRound += 1

            if room.currentRound <= room.maxRounds:
                word = random.choice(words)

                room.word = word
                players_sorted = room.players.order_by("id")

                room.turnIndex = (idx + 1) % players_sorted.count()
                print(room.turnIndex)
                room.turn = players_sorted[room.turnIndex]
                room.save()
                print(RoomSerializer(room).data)
                self.send_message_to_room(
                    room_name, "change.turn", "", RoomSerializer(room).data
                )
            else:
                self.send_message_to_room(
                    room_name, "show.leaderboard", "", RoomSerializer(room).data
                )
        except Room.DoesNotExist:
            self.send_not_correct_game_event("Room does not exist.")

    def receive(self, text_data=None, bytes_data=None):
        try:
            body = json.loads(text_data)
            event_type = body.get("type", "")
            message = body.get("message", "")
            data = body.get("data", {})

            # Handle create game
            if event_type == "create-game":
                # Handle the "create-game" event
                # Your custom logic for creating a game here
                room_name = data.get("room_name", "")

                if Room.objects.filter(name=room_name).exists():
                    self.send_not_correct_game_event("Room already exists.")
                else:
                    self.create_room(data)

            # Handle join game
            if event_type == "join-game":
                try:
                    room = Room.objects.get(name=data.get("room_name", ""))
                    if room.isJoin == True:
                        player = Player(
                            nickname=data.get("name", ""),
                            channel_name=self.channel_name,
                        )
                        player.save()

                        room.players.add(player)
                        self.add_player_to_room_group(room.name)
                        if room.players.count() == room.occupancy:
                            room.isJoin = False
                            room.save()
                        players_list = list(room.players.all())
                        room.turn = players_list[room.turnIndex]
                        room.save()
                        self.send_message_to_room(
                            room.name,
                            "player.joined",
                            "A new player has joined the room.",
                            RoomSerializer(room).data,
                        )
                    else:
                        self.send_not_correct_game_event(
                            "Room is full please try later."
                        )
                except Room.DoesNotExist:
                    self.send_not_correct_game_event("Room does not exist.")

            # Handle paint game
            if event_type == "paint":
                try:
                    room = Room.objects.get(name=data.get("room_name", ""))
                    self.send_message_to_room(
                        data.get("room_name", ""), "handle.points", "", data
                    )
                except Room.DoesNotExist:
                    self.send_not_correct_game_event("Room does not exist.")

            if event_type == "color-change":
                try:
                    room = Room.objects.get(name=data.get("room_name", ""))
                    self.send_message_to_room(
                        data.get("room_name", ""), "color.change", "", data
                    )
                except Room.DoesNotExist:
                    self.send_not_correct_game_event("Room does not exist.")

            if event_type == "stroke-width":
                try:
                    room = Room.objects.get(name=data.get("room_name", ""))
                    self.send_message_to_room(
                        data.get("room_name", ""), "stroke.width", "", data
                    )
                except Room.DoesNotExist:
                    self.send_not_correct_game_event("Room does not exist.")

            if event_type == "clean-screen":
                try:
                    room = Room.objects.get(name=data.get("room_name", ""))
                    self.send_message_to_room(
                        data.get("room_name", ""), "clean.screen", "", data
                    )
                except Room.DoesNotExist:
                    self.send_not_correct_game_event("Room does not exist.")

            if event_type == "message":
                try:
                    room = Room.objects.get(name=data.get("room_name", ""))
                    if data.get("message", "msg") == data.get("word", "w"):
                        user_player = room.players.get(nickname=data.get("name", ""))

                        # Todo: calculate points
                        if data.get("timeTaken", 0) != 0:
                            user_player.points += round(
                                200 / data.get("timeTaken", 60) * 10
                            )
                            user_player.save()
                            data["points"] = user_player.points
                            data["message"] = "Guessed it!"
                            # data["guessed_user_ctr"] += 1
                            self.send_message_to_room(
                                data.get("room_name", ""),
                                "handle.message",
                                "Guessed it!",
                                data,
                            )
                            self.send(json.dumps({"type": "close-input", "data": {}}))
                            self.check_and_change_turn(data.get("room_name", ""))

                    else:
                        self.send_message_to_room(
                            data.get("room_name", ""),
                            "handle.message",
                            "",
                            data,
                        )

                except Room.DoesNotExist:
                    self.send_not_correct_game_event("Room does not exist.")
            if event_type == "change-turn":
                try:
                    room = Room.objects.get(name=data.get("room_name", ""))
                    self.check_and_change_turn(data.get("room_name", ""))
                    # room = Room.objects.get(name=data.get("room_name", ""))
                    # # print(room.turnIndex, room.players.count())
                    # idx = room.turnIndex
                    # if room.turnIndex + 1 == room.players.count():
                    #     room.currentRound += 1

                    # if room.currentRound <= room.maxRounds:
                    #     r = RandomWords()
                    #     word = r.get_random_word()
                    #     room.word = word
                    #     room.turnIndex = (idx + 1) % room.players.count()
                    #     print(room.turnIndex)
                    #     room.turn = room.players.all()[room.turnIndex]
                    #     print(room.turn)
                    #     print(self.channel_name)

                    #     room.save()
                    #     self.send_message_to_room(
                    #         data.get("room_name", ""),
                    #         "change.turn",
                    #         "",
                    #         RoomSerializer(room).data,
                    #     )
                    # else:
                    #     self.send_message_to_room(
                    #         data.get("room_name", ""),
                    #         "show.leaderboard",
                    #         "",
                    #         RoomSerializer(room).data,
                    #     )

                    # self.send_message_to_room(
                    #     data.get("room_name", ""), "change.turn", "", data
                    # )
                except Room.DoesNotExist:
                    self.send_not_correct_game_event("Room does not exist.")

            if event_type == "update-score":
                try:
                    room = Room.objects.get(name=data.get("room_name", ""))
                    self.send_message_to_room(
                        data.get("room_name", ""),
                        "update.score",
                        "",
                        RoomSerializer(room).data,
                    )
                except Room.DoesNotExist:
                    self.send_not_correct_game_event("Room does not exist.")

            # handle color change
        except json.JSONDecodeError:
            print("JSon error encounterd")
            # Handle invalid JSON format
            pass

    def send_not_correct_game_event(self, message):
        self.send(
            text_data=json.dumps({"type": "not-correct-game", "message": message})
        )

    def send_generic_error_event(self, message):
        self.send(text_data=json.dumps({"type": "error", "message": message}))

    def create_room(self, data):
        # Extract relevant data from the client's data
        room_name = data.get("room_name", "")
        max_rounds = data.get("max_rounds", 10)  # Default to 10 if not provided
        occupancy = data.get("room_size", 4)  # Default to 4 if not provided

        # # Generate random words for the room
        r = RandomWords()
        word = r.get_random_word()

        # # Create the room and save it to the database
        room = Room(
            name=room_name,
            maxRounds=max_rounds,
            occupancy=occupancy,
            word=word,
        )
        player = Player.objects.create(
            nickname=data.get("name", ""),
            isPartyLeader=True,
            channel_name=self.channel_name,
        )
        room.save()

        room.players.add(player)
        room.save()
        self.send(
            text_data=json.dumps(
                {"event": "game-created", "message": "Game created successfully."}
            )
        )
        self.add_player_to_room_group(room_name)

        self.send_message_to_room(
            room_name,
            "player.joined",
            "A new player has joined the room.",
            RoomSerializer(room).data,
        )

        # Send a success event back to the client

    def add_player_to_room_group(self, room_name):
        # Add the player to the room's channel group
        async_to_sync(self.channel_layer.group_add)(room_name, self.channel_name)

    def send_message_to_room(self, room_name, event_type, message, data={}):
        # Send a message to the room's channel group
        async_to_sync(self.channel_layer.group_send)(
            room_name,
            {
                "type": event_type,
                "message": message,
                "data": data,
            },
        )

    # custom event handlers
    def player_joined(self, event):
        data = event.get("data", {})
        message = event.get("message", "")
        as_str = json.dumps({"type": "update-room", "message": message, "data": data})
        self.send(
            json.dumps(
                {
                    "type": "update-room",
                    "message": message,
                    "data": data,
                }
            )
        )

    def handle_points(self, event):
        data = event.get("data", {})
        self.send(json.dumps({"type": "points", "data": data}))

    def color_change(self, event):
        data = event.get("data", {})
        self.send(json.dumps({"type": "color-change", "data": data}))

    def stroke_width(self, event):
        data = event.get("data", {})
        self.send(json.dumps({"type": "stroke-width", "data": data}))

    def clean_screen(self, event):
        data = event.get("data", {})
        self.send(json.dumps({"type": "clean-screen", "data": data}))

    def handle_message(self, event):
        data = event.get("data", {})
        self.send(json.dumps({"type": "message", "data": data}))

    def change_turn(self, event):
        data = event.get("data", {})
        self.send(json.dumps({"type": "change-turn", "data": data}))

    def update_score(self, event):
        data = event.get("data", {})
        self.send(json.dumps({"type": "update-score", "data": data}))

    def show_leaderboard(self, event):
        data = event.get("data", {})
        self.send(json.dumps({"type": "show-leaderboard", "data": data}))
