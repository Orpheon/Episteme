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

  def get_next_question(self, author):
    if not author.mention in self.predictions:
      return self.questions[0]
    for question in self.questions:
      if not question in self.predictions[author.mention]:
        return question
    return None

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
          status[question] = self.predictions[author.mention][question]
    return status

  def resolve(self, truths):
    scores = {}
    avgconsensus = {q: 0 for q in self.questions}
    avgconsensus_n = {q: 0 for q in self.questions}
    for usermention,predictions in self.predictions.items():
      userscore = 0
      counter = 0
      for question,prediction in predictions.items():
        avgconsensus[question] += prediction
        avgconsensus_n[question] += 1
        if truths[question] == "true":
          userscore += (1-prediction)**2
          counter += 1
        elif truths[question] == "false":
          userscore += prediction**2
          counter += 1
      if counter == 0:
        scores[usermention] = {
          "error": "N/A",
          "completion": 0
        }
      else:
        scores[usermention] = {
          "error": (userscore/counter),
          "completion": len(predictions) / len(truths)
        }
    self.truths = truths
    os.remove(self.path)
    self.path = os.path.join("finishedpredictiongroups", self.name) + ".json"
    self.dump()

    avgscore = 0
    wrong_questions = []
    for question in avgconsensus.keys():
      avgconsensus[question] /= avgconsensus_n[question]
      if truths[question] == "true":
        avgscore += (1-avgconsensus[question])**2
        if avgconsensus[question] < 0.5:
          wrong_questions.append((question, avgconsensus[question], "true"))
      else:
        avgscore += avgconsensus[question]**2
        if avgconsensus[question] > 0.5:
          wrong_questions.append((question, avgconsensus[question], "false"))

    avgscore /= len(avgconsensus)

    scores["Averaged consensus"] = {
      "error": avgscore,
      "completion": len(avgconsensus)
    }

    return scores, wrong_questions


class Episteme(discord.Client):
  PREDICTIONS_CHANNEL_ID = "430872623426174979"

  def __init__(self):
    super().__init__()
    self.activeconversations = {}
    self.predictiongroups = {}

    if not os.path.exists("activepredictiongroups"):
      os.mkdir("activepredictiongroups")
    if not os.path.exists("finishedpredictiongroups"):
      os.mkdir("finishedpredictiongroups")

    for filename in os.listdir("activepredictiongroups"):
      name = filename.replace(".json", "")
      self.predictiongroups[name] = PredictionGroup(name)


  def render_status(self, author, predictiongroup):
    status = predictiongroup.get_predictions(author)
    output = []
    for question, prediction in status.items():
      if prediction == "?":
        output.append("{0}\t?".format(question))
      else:
        output.append("{0}\t{1}%".format(question, int(100*prediction)))
    return "\n".join(output)


  async def handle_update_request(self, message):
    words = message.content.split()
    if words[1] in self.predictiongroups:
      group = self.predictiongroups[words[1]]
      question = " ".join(words[2:-1])
      if question in group.questions:
        if isnumber(words[-1]):
          prediction = float(words[-1]) / 100
          if 0 <= prediction and prediction <= 1:
            group.set_prediction(message.author, question, prediction)
            await self.send_message(message.channel, "Successfully updated!")
            overview = self.render_status(message.author, group)
            while len(overview) >= 2000:
              idx = overview[:2000].rfind("\n")
              await self.send_message(message.channel, overview[:idx])
              overview = overview[idx:]
            await self.send_message(message.channel, overview)
          else:
            await self.send_message(message.channel, "That prediction is out of the valid range 0-100. Please try again.")
        else:
          await self.send_message(message.channel, "{0} is not a valid number from 0-100. Please try again.".format(words[-1]))
      else:
        await self.send_message(message.channel,
                          "{0} was not recognized as a question of {1}. Please try again.".format(question, group.name))
    else:
      await self.send_message(message.channel, "{0} is not a currently active prediction group. Please try again.".format(words[1]))


  async def handle_prediction_conversation(self, message):
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

    nextquestion = group.get_next_question(message.author)
    if nextquestion:
      self.activeconversations[message.author]["currentquestion"] = nextquestion
      await self.send_message(message.channel, "\n"+nextquestion)
    else:
      del self.activeconversations[message.author]
      await self.send_message(message.channel, """\nCongratulations, you have successfully completed this prediction group.""" +
      """\nYou will be pinged when the results are announced, thank you for participating!""" +
      """\nYou can update predictions with ```update {0} <question> <new prediction>``` at any time in PM.""".format(group.name))
      channels = self.get_all_channels()
      for channel in channels:
        if channel.id == self.PREDICTIONS_CHANNEL_ID:
          await self.send_message(channel, "{0} has successfully set predictions for {1}!".format(message.author.mention, group.name))


  async def handle_resolving_conversation(self, message):
    group = self.activeconversations[message.author]["currentpredictiongroup"]
    question = self.activeconversations[message.author]["currentquestion"]
    if message.content == "true" or message.content == "false" or message.content == "unknown":
      self.activeconversations[message.author]["truths"][question] = message.content
      nextquestion = None
      for question in group.questions:
        if question not in self.activeconversations[message.author]["truths"]:
          nextquestion = question
          break
      if nextquestion:
        self.activeconversations[message.author]["currentquestion"] = nextquestion
        await self.send_message(message.channel, nextquestion)
      else:
        await self.send_message(message.channel, "Finished resolving, calculating scores..")
        results, wrong_questions = group.resolve(self.activeconversations[message.author]["truths"])
        ranking = sorted(list(results.items()), key=lambda x: x[1]["error"])
        channels = self.get_all_channels()
        for channel in channels:
          if channel.id == self.PREDICTIONS_CHANNEL_ID:
            await self.send_message(channel, "{0} has been completed, results will now be published.".format(group.name))
            await self.send_message(channel,
                                    "\n".join(["{0}: error {1}, completed {2}%".format(mention, data["error"],
                                                                                 int(data["completion"]*100)) for mention, data in ranking]))
            await self.send_message(channel, "Following questions have been predicted wrongly by group consensus:")
            await self.send_message(channel,
                                    "\n".join([
                                      "{0}: Predicted at {1} but in reality {2}".format(q[0], q[1], q[2]) for q in wrong_questions
                                    ]))
        del self.activeconversations[message.author]
        del self.predictiongroups[group.name]

    else:
      await self.send_message(message.channel, "Please answer with `true`, `false` or `unknown`.")
      await self.send_message(message.channel, self.activeconversations[message.author]["currentquestion"])


  async def handle_creating_conversation(self, message):
    group = self.activeconversations[message.author]["currentpredictiongroup"]
    if message.content == "finished":
      self.predictiongroups[group.name] = group
      group.dump()
      await self.send_message(message.channel, "Thank you, all questions have been written to disk. {} is now open for predictions.".format(group.name))
      channels = self.get_all_channels()
      for channel in channels:
        if channel.id == self.PREDICTIONS_CHANNEL_ID:
          await self.send_message(channel, "New survey {0} is now available for setting predictions!".format(group.name))
    else:
      if message.content in group.questions:
        await self.send_message(message.channel, "That question already exists.")
      else:
        group.questions.append(message.content)
        await self.send_message(message.channel, "Registered. Next question please (or finish with `finished`).")


  async def on_message(self, message):
    if not message.author.bot:
      if message.channel.is_private:
        if message.author not in self.activeconversations:
          words = message.content.split()
          if len(words) >= 4:
            if words[0] == "update":
              await self.handle_update_request(message)
              return
          await self.send_message(message.channel,
                                  "You have not yet started a prediction conversation, please go to #predictions and ping `@Episteme predict <desired predictiongroup>` to start." +
                                  "\nAlternatively, if you wish to update an existing prediction, please enter ```update <predictiongroup> <question> <new prediction>```")
        else:
          if self.activeconversations[message.author]["currentmode"] == "predicting":
            await self.handle_prediction_conversation(message)
          elif self.activeconversations[message.author]["currentmode"] == "resolving":
            await self.handle_resolving_conversation(message)
          elif self.activeconversations[message.author]["currentmode"] == "creating":
            await self.handle_creating_conversation(message)
      else:
        if self.user.mentioned_in(message):
          words = message.content.split()
          if len(words) >= 3:
            if words[1] == "predict":
              if words[2] in self.predictiongroups:
                group = self.predictiongroups[words[2]]
                nextquestion = group.get_next_question(message.author)
                if not nextquestion:
                  await self.send_message(message.channel,
                                          "You have already given a prediction to all questions of this group.")
                else:
                  self.activeconversations[message.author] = {}
                  self.activeconversations[message.author]["currentpredictiongroup"] = group
                  self.activeconversations[message.author]["currentquestion"] = nextquestion
                  self.activeconversations[message.author]["currentmode"] = "predicting"
                  await self.send_message(message.author,
                                          "Welcome.\nPlease answer every question with a number 0-100 indicating your confidence that it is true.")
                  await self.send_message(message.author, nextquestion)
              else:
                await self.send_message(message.channel,
                                        "Could not find a prediction group named {0}. List: {1}".format(words[2],
                                                                                                        " ".join(self.predictiongroups.keys())))
            elif words[1] == "resolve":
              if words[2] in self.predictiongroups:
                group = self.predictiongroups[words[2]]
                question = group.questions[0]
                self.activeconversations[message.author] = {}
                self.activeconversations[message.author]["currentpredictiongroup"] = group
                self.activeconversations[message.author]["currentquestion"] = question
                self.activeconversations[message.author]["currentmode"] = "resolving"
                self.activeconversations[message.author]["truths"] = {}
                await self.send_message(message.author,
                                        "Welcome.\nPlease answer every question with either `true`, `false` or `unknown`.")
                await self.send_message(message.author, question)
            elif words[1] == "create":
              if words[2] in self.predictiongroups:
                await self.send_message(message.channel, "This prediction group already exists!")
              else:
                self.activeconversations[message.author] = {}
                self.activeconversations[message.author]["currentpredictiongroup"] = PredictionGroup(words[2])
                self.activeconversations[message.author]["currentmode"] = "creating"
                await self.send_message(message.author,
                                        "Welcome.\nPlease enter every question you wish to add to this group, in order, and end with `finished`.")
            elif words[1] == "submit":
              if len(words) >= 4:
                if words[2] in self.predictiongroups:
                  group = self.predictiongroups[words[2]]
                  newquestion = " ".join(words[3:])
                  if newquestion not in group.questions:
                    group.questions.append(newquestion)
                    group.dump()
                    await self.send_message(message.channel,
                                            "`{0}` successfully added to {1}.".format(newquestion, group.name))
                  else:
                    await self.send_message(message.channel, "This question already exists in {}.".format(group.name))
                else:
                  await self.send_message(message.channel, "No prediction group named {} was found.".format(words[2]))
              else:
                await self.send_message(message.channel,
                                        "Not enough arguments for submit command. Proper format `submit <predictiongroup> <new question>`")
            else:
              await self.send_message(message.channel, "Unrecognized command.")
          else:
            await self.send_message(message.channel, "Not enough arguments - have you forgotten to mention the prediction group?")

discordclient = Episteme()
discordclient.run(clientdata["token"])