import json
import discord
import os
import random

with open("client_data.json", "r") as f:
  clientdata = json.load(f)

def isnumber(x):
  try:
    float(x)
    return True
  except:
    return False

class PredictionGroup:
  NONEXISTENT_QUESTION = -1
  PREDICTIONGROUP_RESOLVED = -2

  def __init__(self, name):
    self.name = name
    self.path = os.path.join("activepredictiongroups", self.name) + ".json"
    if not os.path.exists(self.path):
      self.questions = []
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

  def get_predictions(self, author):
    status = {}
    for question in self.questions:
      status[question] = "?"
      if author.mention in self.predictions:
        if question in self.predictions[author.mention]:
          status[question] = self.predictions[author.mention]
    return status

  def resolve(self, truths):
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

  def render_status(self, author, predictiongroup):
    status = predictiongroup.get_predictions(author)
    output = []
    for question, prediction in status.items():
      if prediction == "?":
        output.append("{0}\t?".format(question))
      else:
        output.append("{0}\t{1}%".format(question, int(100*prediction)))
    return "\n".join(output)

  async def on_private_message(self, message):
    if (message.author not in self.activeconversations):
      words = message.content.split()
      if len(words) >= 4:
        if words[0] == "update":
          if words[1] in self.predictiongroups:
            group = words[1]
            question = " ".join(words[2:-1])
            if question in group:
              if isnumber(words[-1]):
                group.set_prediction(message.author, question, float(words[-1]) / 100)
                await self.send_message(message.channel, "Successfully updated!")
                overview = self.render_status(message.author, group)
                while len(overview) >= 2000:
                  idx = overview[:2000].rfind("\n")
                  await self.send_message(message.channel, overview[:idx])
                  overview = overview[idx:]
                await self.send_message(message.channel, overview)
              else:
                await self.send_message(message.channel, "{0} is not a valid number from 0-100".format(words[-1]))
            else:
              await self.send_message(message.channel,
                                      "{0} was not recognized as a question of {1}".format(question, group.name))
          else:
            await self.send_message(message.channel, "{0} is not a currently active prediction group".format(words[1]))
          return
      await self.send_message(message.channel,
                              """You have not yet started a prediction conversation, please go to #predictions and ping `@Episteme predict <desired predictiongroup>` to start.""" +
                              """\nAlternatively, if you wish to update an existing prediction, please enter ```update {0} <question> <new prediction>```""")
      return

    try:
      prediction = float(message.content) / 100
    except TypeError:
      await self.send_message(message.channel,
                              "That was not recognized as a number, please give a valid number between 0 and 100.")
      return

    if not (0 <= prediction and prediction <= 1):
      await self.send_message(message.channel,
                              "That number was out of range. Please give a number between 0 and 100.")
      return

    group = self.activeconversations[message.author]["currentpredictiongroup"]
    question = self.activeconversations[message.author]["currentquestion"]
    errorcode = group.set_prediction(message.author, question, prediction)
    if errorcode == group.NONEXISTENT_QUESTION:
      await self.send_message(message.channel,
                              "Something went wrong, {0} is not a valid question of {1}, which shouldn't happen. Please report this to Orpheon.".format(question, group.name))
    elif errorcode == group.PREDICTIONGROUP_RESOLVED:
      await self.send_message(message.channel, "The survey has been resolved in the meantime. See results in #prediction.")

    overview = self.render_status(message.author, group)
    while len(overview) >= 2000:
      idx = overview[:2000].rfind("\n")
      await self.send_message(message.channel, overview[:idx])
      overview = overview[idx:]
    await self.send_message(message.channel, overview)

    openquestions = [question for question,prediction in group.get_predictions(message.author) if prediction == "?"]
    if len(openquestions) > 0:
      nextquestion = random.choice(openquestions)
      await self.send_message(message.channel, "\n"+nextquestion)
    else:
      await self.send_message(message.channel, """\nCongratulations, you have successfully completed this prediction group.""" +
      """\nYou will be pinged when the results are announced, thank you for participating!""" +
      """\nYou can update predictions with ```update {0} <question> <new prediction>``` at any time in PM.""".format(group.name))


  # async def on_public_message(self, message):

discordclient = Episteme()
discordclient.run(clientdata["token"])