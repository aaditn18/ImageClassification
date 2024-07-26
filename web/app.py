from flask import Flask, jsonify, request
from flask_restful import Api, Resource
from pymongo import MongoClient
import os
import bcrypt
import numpy as np
import requests

from keras.applications import InceptionV3
# imports inception_v3 model pretrained on images from imagenet for image classification ^
from keras.applications.inception_v3 import preprocess_input
# imports preprocess function which does some cleaning and preprocessing of image before using Inception_v3 ^
from keras.applications import imagenet_utils
# provides utilities (like decoding prediction) for models like Inception_v3 which have been trained on imagenet dataset ^
from tensorflow.keras.preprocessing.image import img_to_array
# Converts PIL image to numpy array ^
from PIL import Image
# Converts stream image into PIL image ^
from io import BytesIO
# Converts https url address into a stream which can be used by PIL image ^

app = Flask(__name__) 
api = Api(app)

# Access your Flask application using the new port in your browser or API client:
# http://localhost:5002

pretrained_model = InceptionV3(weights = "imagenet") # loading pre-trained model


client = MongoClient("mongodb://db:27017")
db = client.ImageClassificationDB             # db init
users = db['Users']                           # collection init

class Register(Resource):
    def post(self):
        input_data = request.get_json()
        username = input_data["username"]
        pwd = input_data["pwd"]
        
        # check if username already exists, pwd is proper or not
        if users.find_one({"username":username}) is not None:
            # Use .count() == 0 to check using .find()
            return jsonify({
            "Status": 301,
            "Message": "Username already in use"
        })
        if len(pwd) < 8:
            return jsonify({
            "Status": 302,
            "Message": "Pwd too short"
        })
        hashed_pw = bcrypt.hashpw(pwd.encode('utf8'), bcrypt.gensalt())
        users.insert_one({
            "username" : username,
            "pwd" : hashed_pw,
            "tokens" : 4

        })

        ret = {
            "Status": 200,
            "Message": "Successful API Registration"
        }

        return jsonify(ret)
    
def verifyPwd(username, pwd):
    hashed_pwd = users.find({"username":username})[0]["pwd"]
    return bcrypt.hashpw(pwd.encode('utf8'), hashed_pwd) == hashed_pwd

def countTokens(username):
    return users.find({"username": username})[0]["tokens"]
    

class Classify(Resource):
    def post(self):
        input_data = request.get_json()
        username = input_data["username"]
        pwd = input_data["pwd"]
        if users.find_one({"username": username}) is None or not verifyPwd(username, pwd):
            return jsonify({
                "status: ":302,
                "message: ": "incorrect username/pwd"
            })
        tokens = countTokens(username)
        if tokens <= 0:
            return jsonify({
                "status: ":301,
                "message: ": "Insufficient tokens, please refill!"
            })
        
        # Classification
        url = input_data['url']
        if not url: 
            return jsonify({
                "status: ": 400,
                "message: ": "incorrect url"                
            })

        # Load image from URL
        response = requests.get(url) #downloading image from url
        img = Image.open(BytesIO(response.content)) 
        # converting image into byte stream form which can then be opened by PIL Image


        # Pre-process the image
        img = img.resize((299,299)) #expected size by v3
        img_arr = img_to_array(img) #conversion to np array
        img_arr = np.expand_dims(img_arr, axis=0) #dimension added to represent batch size for model
        # Array values scaled ^
        img_arr = preprocess_input(img_arr)

        # Make Prediction

        prediction = pretrained_model.predict(img_arr)
        final_prediction = imagenet_utils.decode_predictions(prediction, top=5)
        # get top 5 possiblities of what obj can be^
        '''
        Example of value final_prediction can take:
        [
            [
        ('n02504458', 'African_elephant', 0.826),
        ('n01871265', 'tusker', 0.102),
        ('n02504013', 'Indian_elephant', 0.052),
        ('n02099601', 'golden_retriever', 0.012),
        ('n02123159', 'tiger_cat', 0.008)
            ]
        ]
        '''
        max = {"name": "", "val":0}
        for tup in final_prediction[0]:
            if tup[2] > max["val"]:
                max["val"] = tup[2]
                max["name"] = tup[1]
            
        users.update_one({'username':username}, {
            "$set":{"tokens": tokens -1}
        })
        return jsonify({
            "Status " : 200,
            "Result " : f"Object: {max['name']}, Likelihood: {100*max['val']} %",
            "Tokens Remaining": tokens-1
        })
    
class Refill(Resource):
    def post(self):
        input_data = request.get_json()
        username = input_data["username"]
        auth_pwd =  input_data["auth_pwd"]
        if users.find_one({"username": username}) is None:
            return jsonify({
                "status: ":302,
                "message: ": "incorrect username"
            })

        # check auth, hardcoded for now, not irw projects
        correct_pwd = "13dbjhq182rhc"
        if auth_pwd != correct_pwd:
            return jsonify({
                "status: ":303,
                "message: ": "incorrect admin pwd"
            })            


        tokens = countTokens(username)
        newTokens = input_data["new_tokens"]   
        users.update_one({'username':username}, {
            "$set":{"tokens": tokens + newTokens}
        })

        return jsonify({
            "Status " : 200,
            "Message": "Refill successful"
        })   
         
api.add_resource(Register, "/register")
api.add_resource(Classify, "/classify")
api.add_resource(Refill, "/refill")

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5004)