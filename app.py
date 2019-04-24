from flask import Flask, render_template, request, session, redirect, url_for, send_file
import sys
import os
import uuid
import hashlib
import pymysql.cursors
from functools import wraps
import time

app = Flask(__name__)
app.secret_key = "super secret key"
IMAGES_DIR = os.path.join(os.getcwd(), "images")

connection = pymysql.connect(host="localhost",
                             user="root",
                             password="",
                             db="finstagram",
                             charset="utf8mb4",
                             port=3306,
                             cursorclass=pymysql.cursors.DictCursor,
                             autocommit=True)

def login_required(f):
    @wraps(f)
    def dec(*args, **kwargs):
        if not "username" in session:
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return dec

@app.route("/")
def index():
    if "username" in session:
        return redirect(url_for("home"))
    return render_template("index.html")

@app.route("/home")
@login_required
def home():
    return render_template("home.html", username=session["username"])

@app.route("/upload", methods=["GET"])
@login_required
def upload():
    return render_template("upload.html")

@app.route("/images", methods=["GET"])
@login_required
def images():
    query = "SELECT * FROM photo WHERE allFollowers = 1 OR photoOwner = %s OR photoID in (SELECT photoID FROM share NATURAL JOIN belong WHERE belong.username = %s AND share.groupName = belong.groupName) ORDER BY timestamp desc"
    with connection.cursor() as cursor:
        cursor.execute(query, (session["username"], session["username"]))
    data = cursor.fetchall()
    return render_template("images.html", images=data)

@app.route("/image/<image_name>", methods=["GET"])
def image(image_name):
    image_location = os.path.join(IMAGES_DIR, image_name)
    if os.path.isfile(image_location):
        return send_file(image_location, mimetype="image/jpg")

@app.route("/login", methods=["GET"])
def login():
    return render_template("login.html")

@app.route("/register", methods=["GET"])
def register():
    return render_template("register.html")

@app.route("/addfriends", methods=["GET"])
@login_required
def addfriends():
    query = "SELECT groupname FROM closefriendgroup WHERE groupOwner=%s"
    with connection.cursor() as cursor:
        cursor.execute(query, session["username"])
    data = cursor.fetchall()
    return render_template("addfriends.html", closefriendgroups=data)

@app.route("/loginAuth", methods=["POST"])
def loginAuth():
    if request.form:
        requestData = request.form
        username = requestData["username"]
        plaintextPasword = requestData["password"]
        hashedPassword = hashlib.sha256(plaintextPasword.encode("utf-8")).hexdigest()

        with connection.cursor() as cursor:
            query = "SELECT * FROM person WHERE username = %s AND password = %s"
            cursor.execute(query, (username, hashedPassword))
        data = cursor.fetchone()
        if data:
            session["username"] = username
            return redirect(url_for("home"))

        error = "Incorrect username or password."
        return render_template("login.html", error=error)

    error = "An unknown error has occurred. Please try again."
    return render_template("login.html", error=error)

@app.route("/followUser", methods=["POST"])
@login_required
def followUser():
    if request.form:
        requestData = request.form
        followerUsername = requestData["followUser"]
        try:
            with connection.cursor() as cursor:
                query = "INSERT INTO follow (followeeUsername, followerUsername, acceptedfollow) VALUES (%s, %s, %s)"
                cursor.execute (query, (followerUsername, session["username"], 0))
            message = "Request sent successfully"
            return render_template("home.html", message=message)
        except:
            message = "Error following user"
            return render_template("home.html", message=message)

@app.route("/followrequests", methods=["GET"])
@login_required
def followrequests():
    with connection.cursor() as cursor:
        cursor.execute("SELECT * FROM follow WHERE followeeUsername = %s AND acceptedfollow = %s", (session["username"], 0))
        followrequests = cursor.fetchall()
        return render_template('followrequests.html', followrequests = followrequests)

@app.route("/acceptFollow", methods=["POST"])
@login_required
def acceptFollow():
    if request.form:
        followeeUsername = session["username"]
        query = "SELECT followerUsername FROM follow WHERE followeeUsername=%s AND acceptedfollow=%s"
        with connection.cursor() as cursor: 
            cursor.execute(query, (followeeUsername, 0))
        data = cursor.fetchall()

        for followerUsername in data:
            action = request.form["action" + followerUsername["followerUsername"]]
            with connection.cursor() as cursor:
                if action == "accept":
                    query = "UPDATE follow SET acceptedfollow = %s WHERE followerUsername = %s AND followeeUsername = %s"
                    cursor.execute(query, (1, followerUsername["followerUsername"], session["username"]))
                elif action =="decline":
                    query = "DELETE FROM follow WHERE followerUsername = %s AND followeeUsername = %s"
                    cursor.execute(query, (followerUsername["followerUsername"], session["username"]))
    return redirect(url_for("home") )

@app.route("/tagrequests", methods=["GET"])
@login_required
def tagrequests():
    with connection.cursor() as cursor:
        cursor.execute("SELECT * FROM tag WHERE username=%s AND acceptedtag=%s", (session["username"], 0))
        tagrequests = cursor.fetchall()
        return render_template('tagrequests.html', tagrequests = tagrequests)

@app.route("/acceptTag", methods=["POST"])
@login_required
def acceptTag():
    if request.form:
        username = session["username"]
        data = request.form
        for tag in data:
            action = data
            photoID = tag.strip("action")
            with connection.cursor() as cursor:
                if action == "accept":
                    query = "UPDATE tag SET acceptedfollow = %s WHERE photoID=%s AND username=%s"
                    cursor.execute(query, (1, photoID, username))
                elif action == "decline":
                    query = "DELETE FROM tag WHERE photoID = %s AND username = %s"
                    cursor.execute(query, (photoID, username))
        return redirect(url_for("home"))

@app.route("/registerAuth", methods=["POST"])
def registerAuth():
    if request.form:
        requestData = request.form
        username = requestData["username"]
        plaintextPasword = requestData["password"]
        hashedPassword = hashlib.sha256(plaintextPasword.encode("utf-8")).hexdigest()
        firstName = requestData["fname"]
        lastName = requestData["lname"]
        isPrivate = 0
        if requestData.getlist('isPrivate') != []:
            isPrivate = 1
        bio = requestData["bio"]
        try:
            with connection.cursor() as cursor:
                query = "INSERT INTO person (username, password, fname, lname, bio, isPrivate) VALUES (%s, %s, %s, %s, %s, %s)"
                cursor.execute(query, (username, hashedPassword, firstName, lastName, bio, isPrivate))
        except pymysql.err.IntegrityError:
            error = "%s is already taken." % (username)
            return render_template('register.html', error=error)

        if request.files:
            image_file = request.files.get("avatar", "")
            image_name = image_file.filename
            filepath = os.path.join(IMAGES_DIR, image_name)
            image_file.save(filepath)
            query = "UPDATE person SET avatar = %s WHERE username = %s"
            with connection.cursor() as cursor:
                cursor.execute(query, (image_name, username))
        return redirect(url_for("login"))

    error = "An error has occurred. Please try again."
    return render_template("register.html", error=error)

@app.route("/logout", methods=["GET"])
def logout():
    session.pop("username")
    return redirect("/")

@app.route("/uploadImage", methods=["POST"])
@login_required
def upload_image():
    if request.files:
        image_file = request.files.get("imageToUpload", "")
        image_name = image_file.filename
        filepath = os.path.join(IMAGES_DIR, image_name)
        if request.form:
            requestData = request.form
            caption = requestData["caption"]
            allFollowers = 0
            if requestData.getlist('allFollowers') != []:
                allFollowers = 1
            image_file.save(filepath)
            query = "INSERT INTO photo (timestamp, filePath, caption, photoOwner, allFollowers) VALUES (%s, %s, %s, %s, %s)"
            with connection.cursor() as cursor:
                cursor.execute(query, (time.strftime('%Y-%m-%d %H:%M:%S'), image_name, caption, session["username"], allFollowers))
                print("done");
                if allFollowers == 0:
                    photoID = cursor.lastrowid
                    cursor.execute("SELECT groupName FROM closefriendgroup WHERE groupOWNER=%s", session["username"])
                    groupData = cursor.fetchall()
                    return render_template("upload.html", allFollowers = False, photoID = photoID, groupData = groupData)
            message = "Image has been successfully uploaded."
            return render_template("upload.html", message=message)
    else:
        message = "Failed to upload image."
        return render_template("upload.html", message=message)

@app.route("/createGroup", methods=["POST"])
@login_required
def createGroup():
    if request.form:
        try:
            requestData = request.form
            groupName = requestData["groupName"]
            with connection.cursor() as cursor:
                query = "INSERT INTO closefriendgroup (groupName, groupOwner) VALUES (%s, %s)"
                cursor.execute(query, (groupName, session["username"]))
            message = "Close Friend Group successfully created!"
            return render_template("home.html", groupmessage = message)
        except:
            message = "Error creating Close Friend Group"
            return render_template("home.html", groupmessage = message)

@app.route('/addfriend', methods=["POST"])
@login_required
def addFriend():
    if request.form:
        requestData = request.form
        friend = requestData["friend"]
        select = requestData.get("grouplist")
        query = "INSERT INTO belong (groupName, groupOwner, username) VALUES (%s, %s, %s)"
        fetchquery = "SELECT groupname FROM closefriendgroup WHERE groupOwner=%s"
        with connection.cursor() as cursor:
            cursor.execute(fetchquery, session["username"])
        data = cursor.fetchall()
        try:
            with connection.cursor() as cursor:
                cursor.execute(query, (select, session["username"], friend))
            message = "Friend successfully added to Close Friend Group!"
            return render_template("addfriends.html", closefriendgroups=data, message=message)
        except:
            message = "Error adding friend into Close Friend Group!"
            return render_template("addfriends.html", closefriendgroups=data, message=message)

@app.route('/assignGroups', methods=["POST"])
@login_required
def assignGroups():
    if request.form:
        requestData = request.form
        for group in requestData:
            print(group, file=sys.stderr)
            selected = 0
            if requestData.getlist(group) != []:
                selected = 1
            with connection.cursor() as cursor:
                cursor.execute("SELECT MAX(photoID) FROM photo WHERE allFollowers=0 AND photoOwner=%s", session["username"])
                photoID = cursor.fetchall()
                photoID=photoID[0]["MAX(photoID)"]
                print(photoID, file=sys.stderr)
            if selected == 1:
                with connection.cursor() as cursor:
                    query = ("INSERT INTO share (groupName, groupOwner, photoID) VALUES (%s, %s, %s)")
                    cursor.execute(query, (group, session["username"], photoID))
        message = "Image has been successfully uploaded."
        return render_template("upload.html", message=message)
if __name__ == "__main__":
    if not os.path.isdir("images"):
        os.mkdir(IMAGES_DIR)
    app.run()
