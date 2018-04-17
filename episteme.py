import json
import discord
import os

with open("client_data.json", "r") as f:
  clientdata = json.load(f)

class PredictionGroup:
  NONEXISTENT_QUESTION = -1
  PREDICTIONGROUP_RESOLVED = -2

  def __init__(self, name):
    self.name = name
    self.path = os.path.join("activepredictiongroups", self.name) + ".json"
    if not os.path.exists(self.path):
      self.questions = {}
      self.predictions = {}
      self.truths = {}
      self.dump()
    else:
      self.load()

  def load(self):
    with open(self.path, "r") as f:
      data = json.load(f)
      self.questions = data["questions"]
      self.predictions = data["predictions"]
      self.truths = data["truths"]

  def dump(self):
    with open(self.path, "w") as f:
      data = {
        "questions": self.questions,
        "predictions": self.predictions,
        "truths": self.truths
      }
      json.dump(data, f, indent=4)

  def set_prediction(self, user, question, prediction):
    if question not in self.questions:
      return self.NONEXISTENT_QUESTION
    if len(self.truths) > 0:
      return self.PREDICTIONGROUP_RESOLVED

    if user.mention not in self.predictions:
      self.predictions[user.mention] = {}
    self.predictions[user.mention][question] = prediction
    self.dump()
    return 0

  def resolve_predictions(self, truths):
    scores = {}
    for usermention,predictions in self.predictions.items():
      userscore = 0
      counter = 0
      for question,prediction in predictions.items():
        if truths[question] == "true":
          userscore += (1-prediction)**2
          counter += 1
        elif truths[question] == "false":
          userscore += prediction**2
          counter += 1
      scores[usermention] = {
        "error": userscore/counter,
        "completion": len(predictions) / len(truths)
      }
    self.truths = truths
    os.remove(self.path)
    self.path = os.path.join("finishedpredictiongroups", self.name) + ".json"
    self.dump()

    return scores


class Episteme(discord.Client):
  def __init__(self):
    super().__init__()
    self.activeconversations = {}
    self.predictiongroups = {}

    if not os.path.exists("activepredictiongroups"):
      os.mkdir("activepredictiongroups")
    if not os.path.exists("finishedpredictiongroups"):
      os.mkdir("finishedpredictiongroups")

    for filename in os.listdir("activepredictiongroups"):
      self.predictiongroups[filename] = PredictionGroup(filename)

  # async def on_private_message(self, message):
  # async def on_public_message(self, message):

discordclient = Episteme()
discordclient.run(clientdata["token"])