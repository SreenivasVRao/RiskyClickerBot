import ClarifaiBot
import HiveBot
import operator

class Slave:
    def __init__(self):
        self.clarifai_bot = ClarifaiBot.Bot()
        self.hive_bot = HiveBot.Bot()

    def combine_predictions(self, prediction_1, prediction_2):

        # if Clarifai says violent, it's mostly right.
        # if Hive says anything else, it's mostly right.

        if prediction_1 is not None:
            clarifai_labels = sorted(prediction_1.items(), key=operator.itemgetter(1), reverse=True)

            if clarifai_labels[0][0] is 'Violent':
                status = prediction_1

            elif prediction_2 is not None:
                status = prediction_2

            else:  # if Hive API failed, but Clarifai API worked
                status = prediction_1

        elif prediction_2 is not None:
            status = prediction_2

        else:
            status = None

        return status

    def analyze(self, links):  # TO ARMS! TO ARMS!
        # calls both bots

        prediction_1 = self.clarifai_bot.get_all_predictions(links)
        prediction_2 = self.hive_bot.get_all_predictions(links)

        status = {}
        for aLink in links:
            status[aLink] = self.combine_predictions(prediction_1[aLink], prediction_2[aLink])
        return status

    def analyze_video_frame(self, jpeg_file, b64_frame):

        prediction_1 = self.clarifai_bot.get_prediction(b64_frame, 'b64')
        prediction_2 = self.hive_bot.get_prediction(jpeg_file, 'jpeg')

        return prediction_1, prediction_2
