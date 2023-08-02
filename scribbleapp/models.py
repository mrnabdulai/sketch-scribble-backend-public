from django.db import models
from helpers.models import TrackingModel


class Player(models.Model):
    # Define fields for the player model (playerSchema in the original Mongoose schema)
    nickname = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        default=None,
    )
    isPartyLeader = models.BooleanField(default=False)
    points = models.IntegerField(default=0)

    # Additional fields to handle unique identification using Django Channels
    # socket_id = models.CharField(max_length=255, blank=True, null=True, unique=True)
    channel_name = models.CharField(max_length=255, blank=True, null=True, unique=True)

    def __str__(self):
        return self.nickname or str(self.pk)


# Create your models here.
class Room(TrackingModel):
    # Define fields for the room model (roomSchema in the original Mongoose schema)
    word = models.CharField(max_length=100)  # Corresponds to the 'word' field
    name = models.CharField(
        max_length=100,
        unique=True,
        blank=False,
        null=False,
    )  # Corresponds to the 'name' field
    occupancy = models.IntegerField(default=4)  # Corresponds to the 'occupancy' field
    maxRounds = models.IntegerField()  # Corresponds to the 'maxRounds' field
    currentRound = models.IntegerField(
        default=1
    )  # Corresponds to the 'currentRound' field
    players = models.ManyToManyField(
        Player,
        related_name="rooms",
    )  # Corresponds to the 'players' field with playerSchema
    isJoin = models.BooleanField(default=True)  # Corresponds to the 'isJoin' field
    turn = models.ForeignKey(
        Player, null=True, blank=True, on_delete=models.SET_NULL, related_name="turns"
    )  # Corresponds to the 'turn' field
    turnIndex = models.IntegerField(default=0)  # Corresponds to the 'turnIndex' field
