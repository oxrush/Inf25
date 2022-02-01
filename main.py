from datetime import date, datetime, timedelta
import json
from os import getenv
import re
import secrets
from flask import Flask, render_template, session, request, redirect, url_for, abort, jsonify
from flask_mail import Mail, Message
from flask.helpers import flash
import database
from werkzeug.exceptions import HTTPException
import re
import secrets
from urllib.parse import urlparse, quote_plus

app = Flask(__name__)

app.config.from_json("config.json")

app.url_map.strict_slashes = False # https://stackoverflow.com/questions/33241050/trailing-slash-triggers-404-in-flask-path-rule

mail = Mail(app) # MUST occur after config values are set!

def verification_required(function):
    def wrapper(*args, **kwargs):
        if "verified_email" in session:
            return function(*args, **kwargs)
        else:
            return redirect(url_for("verify_email"))

    wrapper.__name__ = function.__name__
    return wrapper



@app.route("/")
def index():
    if not "courses" in request.args:
        courses = request.cookies.get("courses") or "1and2" # TODO: Move default courses to DB / config
        return redirect(url_for("index", courses=courses, **request.args))

    course_string = request.args["courses"]
    course_ids = course_string.split('and')
    courses = database.get_courses(course_ids)
    
    courses_dict = {}

    for course in courses:
        course["links"] = database.get_links(course["id"])
        courses_dict[course["id"]] = course


    weekly_assignments = database.get_weekly_assignments(course_ids)
    date_assignments = database.get_date_assignments(course_ids)

    return render_template("main.html", courses=courses, courses_dict=courses_dict, quote_plus=quote_plus, weekly_assignments=weekly_assignments, date_assignments=date_assignments, course_string=course_string)
'''
@app.errorhandler(404)
def err_404(e):
    return render_template("404.html"), 404
'''

@app.route("/customise")
def customise():
    course_string = request.args.get("courses") or ""
    course_ids_checked = course_string.split('and')
    courses = database.get_courses()
    for course in courses:
        course["_checked"] = (str(course["id"]) in course_ids_checked)
            
    return render_template("customise.html", courses=courses, course_ids_checked=course_ids_checked, course_string=course_string)

@app.route("/course/<id>")
@verification_required
def course(id):
    course_infos = database.get_courses([id])
    if len(course_infos) == 0:
        abort(404)
    else:
        course_info = course_infos[0] # There can only be one.

    links = database.get_links(id)

    date_assignments = database.get_date_assignments([id])
    weekly_assignments = database.get_weekly_assignments([id])

    return render_template("course.html", course_info=course_info, links=links, date_assignments=date_assignments, weekly_assignments=weekly_assignments)

@app.route("/course/<id>/addlink", methods=["POST"])
@verification_required
def course_add_link(id):
    
    if len(database.get_courses([id])) == 0:
        abort(404) # The course does not exist

    type = request.form["type"]
    precedence = request.form["precedence"]
    title = request.form["title"]
    url = request.form["url"]
    email = session["verified_email"]

    if not title or not url:
        print("Title and url are both required.")
        return "Title and url are both required.", 400

    # TODO: Sanitise data.
    database.add_link(id, type, precedence, url, title, email)

    return "", 204 # No Content


@app.route("/link/<id>", methods=["POST", "DELETE"])
@verification_required
def link(id):
    email = session["verified_email"]
    if request.method == "DELETE":
        database.delete_link(id, email)
        return "", 204 # No Content
    elif request.method == "POST":
        precedence = request.form["precedence"]
        title = request.form["title"]
        url = request.form["url"]

        database.update_link(id, precedence, title, url, email)

        return "", 204 # No Content

@app.route("/course/<id>/addassignment", methods=["POST"])
@verification_required
def course_add_assignment(id):
    
    if len(database.get_courses([id])) == 0:
        abort(404) # The course does not exist

    email = session["verified_email"]

    date = request.form["date"]
    time = request.form["time"]
    name = request.form["name"]

    if len(time) < 6 :
            time += ":00"

    datetime_str = f"{date} {time}"

    database.add_assignment(id, datetime_str, name, email)

    return "", 204 # No Content

@app.route("/assignment/<id>", methods=["POST", "DELETE"])
@verification_required
def assignment(id):
    email = session["verified_email"]
    if request.method == "DELETE":
        database.delete_assignment(id, email)
        return "", 204 # No Content
    elif request.method == "POST":
        date = request.form["date"]
        time = request.form["time"]
        name = request.form["name"]

        if len(time) < 6 :
            time += ":00"

        datetime_str = f"{date} {time}"

        database.update_assignment(id, datetime_str, name, email)

        return "", 204 # No Content

@app.route("/verify", methods=["GET", "POST"])
def verify_email():
    if request.method == "POST":
        username = request.form["login"]
        if re.match(r"^s\d{7}$", username) or username == "oxrush":
            code = secrets.token_hex(8)
            

            address = f"{username}@inf.ed.ac.uk"

            if username == "oxrush":
                address = "oxrush@maya.cx"


            database.cancel_login_code(address)
            database.add_login_code(address, code)

            msg = Message("Login code for Inf'25 Dashboard", sender="Inf25 Dashboard Email Verification <inf25-dashboard@maya.cx>" ,recipients=[address])
            msg.html = render_template("code_email.html", code=code)
            mail.send(msg)

            session["verification_claimed_email"] = address

            return redirect(url_for("verify_code"))

        else:
            flash("Invalid username.")
            return redirect(url_for("verify_email"))

    return render_template("verify.html")

@app.route("/verify/code", methods=["GET", "POST"])
def verify_code():
    claimed_email = session["verification_claimed_email"]

    if database.count_failed_logins(claimed_email, "-1 hour") >= 8:
            abort(429)

    correct_code = database.get_login_code(claimed_email)

    if correct_code is None:
        return redirect(url_for("verify_email"))

    if request.method == "POST":

        claimed_code = request.form["code"]

        if claimed_code == correct_code:
            database.cancel_login_code(claimed_email)
            session["verified_email"] = claimed_email
            session.pop("verification_claimed_email")
            
            return redirect(url_for("contribute"))
        else:
            database.add_failed_login(claimed_email)

            flash("Incorrect code. Please enter it again or go back and request a new code.", "error")
            return redirect(url_for("verify_code"))

    return render_template("verify_code.html", claimed_email=claimed_email)

@app.route("/unverified")
def unverified_forward():
    url = request.args["url"]
    p_url = urlparse(url)

    domain = p_url.netloc
    scheme = p_url.scheme

    trusted = database.is_trusted_domain(domain) and scheme in ["http", "https"]

    print(trusted)

    if trusted:
        return redirect(url)
    
    return render_template("untrusted.html", url=url)

@app.route("/contribute")
@verification_required
def contribute():
    courses = database.get_courses()
    return render_template("contribute.html", courses=courses)

@app.route("/api/assignments")
def api_assignments():
    s_from = request.args["from"]
    s_to = request.args["to"]
    courses = request.args["courses"].split("and")

    weekday_from = datetime.strptime(s_from, "%Y-%m-%d %H:%M:%S").strftime("%w")
    weekday_to = datetime.strptime(s_to, "%Y-%m-%d %H:%M:%S").strftime("%w")

    time_from = s_from.split(" ")[1]
    time_to = s_to.split(" ")[1]

    date_assignments = database.get_date_assignments(courses, s_from, s_to)
    weekly_assignments = database.get_weekly_assignments(courses, weekday_from, time_from, weekday_to, time_to)

    assignments = date_assignments + weekly_assignments
    return jsonify(assignments)


@app.route("/logout", methods=["POST"])
def logout():
    session.clear()
    return redirect(url_for("index"))

@app.errorhandler(404)
def err_404(error):
    print(type(error))
    return render_template("errors/404.html"), 404

@app.errorhandler(HTTPException)
def err_handler(err):
    return render_template("errors/generic.html", error=err), err.code
    
if __name__ == "__main__":
    app.run(debug=True)