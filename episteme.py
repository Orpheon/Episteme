import json
import discord
import os

with open("client_data.json", "r") as f:
  clientdata = json.load(f)

class PredictionGroup:
  def __init__(self, name):
    self.name = name
    self.path = os.path.join("predictiongroups", self.name) + ".json"
    if not os.path.exists(self.path):
      self.questions = {}
      self.predictions = {}
      self.resolved = False
      self.dump()
    else:
      self.load()

  def load(self):
    with open(self.path, "r") as f:
      data = json.load(f)
      self.questions = data["questions"]
      self.predictions = data["predictions"]
      self.resolved = data["resolved"]

  def dump(self):
    with open(self.path, "w") as f:
      data = {
        "questions": self.questions,
        "predictions": self.predictions,
        "resolved": self.resolved
      }
      json.dump(data, f, indent=4)

class Episteme(discord.Client):
  def __init__(self):
    super().__init__()
    self.activeconversations = {}
    self.predictiongroups = {}

    if not os.path.exists("predictiongroups"):
      os.mkdir("predictiongroups")
    else:
      for filename in os.listdir("predictiongroups"):
        self.predictiongroups[filename] = PredictionGroup(filename)

  # async def on_private_message(self, message):
  # async def on_public_message(self, message):

discordclient = Episteme()
discordclient.run(clientdata["token"])