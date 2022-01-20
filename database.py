from calendar import SATURDAY, SUNDAY
import sqlite3


def __db_connect():
    return sqlite3.connect("db.sqlite3")

def get_courses(ids=None):
    conn = __db_connect()
    cur = conn.cursor()

    try:
        if ids is None:
            query = """
                SELECT id, shortname, name, dprs_id
                FROM Course
            """
            results = cur.execute(query)

        else:
            query = """
                SELECT id, shortname, name, dprs_id
                FROM Course
                WHERE id IN ({})
            """.format(','.join('?'*len(ids)))

            results = cur.execute(query, ids)

        courses = []
        for (id, shortname, name, dprs_id) in results:
            courses.append({
                "id": id,
                "shortname": shortname,
                "name": name,
                "dprs_id": dprs_id
            })
    finally:
        conn.close()

    return courses

def get_links(course_id):

    conn = __db_connect()
    cur = conn.cursor()

    try:
        query = """
            SELECT id, type, precedence, url, name, verified
            FROM CourseLink cl
            WHERE course_id = ?
                AND deleted = 0
                AND revision = (SELECT max(cl2.revision) FROM CourseLink cl2 WHERE cl2.id = cl.id)
            ORDER BY precedence ASC
        """

        results = cur.execute(query, (course_id,))

        links = {}
        for id, type, precedence, url, name, verified in results:
            if not type in links:
                links[type] = []
            links[type].append((id, precedence, url, name, verified))

    finally:
        conn.close()

    return links

def is_trusted_domain(domain):

    conn = __db_connect()
    cur = conn.cursor()

    try:
        query = """
            SELECT count(domain)
            FROM TrustedDomain
            WHERE domain = ?
        """

        trusted = list(cur.execute(query, (domain,)))[0][0] == 1

    finally:
        conn.close()

    return trusted

def add_link(course_id, type, precedence, url, name, email):
    conn = __db_connect()
    cur = conn.cursor()

    try:
        query = """
            INSERT INTO CourseLink (id, revision, course_id, type, precedence, url, name, editor_username)
            VALUES (
                coalesce ((SELECT max(id) FROM CourseLink), 0) + 1,
                1, ?, ?, ?, ?, ?, ?
            )
        """

        cur.execute(query, (course_id, type, precedence, url, name, email))

        conn.commit()

    finally:
        conn.close()

def delete_link(id, email):
    conn = __db_connect()
    cur = conn.cursor()

    try:
        query = """
            INSERT INTO CourseLink (id, revision, deleted, editor_username)
            VALUES (
                ?,
                (SELECT max(revision) FROM CourseLink WHERE id = ?) + 1,
                1, ?
            )
        """
        cur.execute(query, (id, id, email))

        conn.commit()

    finally:
        conn.close()

def update_link(id, precedence, title, url, email):
    conn = __db_connect()
    cur = conn.cursor()

    try:
        query = """
            INSERT INTO CourseLink (id, revision, course_id, type, precedence, name, url, editor_username)
            VALUES (
                ?,
                (SELECT max(revision) FROM CourseLink WHERE id = ?) + 1,
                (SELECT course_id FROM CourseLink WHERE id = ?),
                (SELECT type FROM CourseLink WHERE id = ?),
                ?, ?, ?, ?
            )
        """
        cur.execute(query, (id, id, id, id, precedence, title, url, email))

        conn.commit()

    finally:
        conn.close()

def add_login_code(username, code):
    conn = __db_connect()
    cur = conn.cursor()

    try:
        query = """
            INSERT INTO LoginCode (username, code, expiry, cancelled)
                VALUES (?, ?, datetime('now', '+20 minutes'), 0)
        """

        cur.execute(query, (username, code))

        conn.commit()
    
    finally:
        conn.close()

def cancel_login_code(username):
    conn = __db_connect()
    cur = conn.cursor()

    try:
        query = """
            UPDATE LoginCode
            SET cancelled = 1
            WHERE username = ?
        """
        cur.execute(query, (username,))

        conn.commit()
    
    finally:
        conn.close()

def get_login_code(username):
    conn = __db_connect()
    cur = conn.cursor()

    try:
        query = """
            SELECT code FROM LoginCode
            WHERE username = ?
                AND expiry > datetime('now')
                AND cancelled = 0
        """

        codes = list(cur.execute(query, (username,)))

        conn.commit()
    
    finally:
        conn.close()

    if len(codes) == 0:
        return None
    elif len(codes) == 1:
        return codes[0][0]
    else:
        raise AssertionError("There can only be one valid login code per username at a time.")
            

def add_failed_login(username):
    conn = __db_connect()
    cur = conn.cursor()

    try:
        query = """
            INSERT INTO FailedLogin (username, timestamp)
            VALUES (?, datetime('now'))
        """
        
        cur.execute(query, (username,))

        conn.commit()
    
    finally:
        conn.close()


def count_failed_logins(username, since):
    conn = __db_connect()
    cur = conn.cursor()

    try:
        query = """
            SELECT count(id) FROM FailedLogin
            WHERE username = ?
                AND timestamp > datetime('now', ?)

        """

        count = list(cur.execute(query, (username, since)))[0][0]

        conn.commit()
    
    finally:
        conn.close()

    return count

def __parse_assignments(results):
    assignments = []
    for (id, course_id, time, name) in results:
        assignments.append({
            "id": id,
            "course_id": course_id,
            "datetime": time,
            "name": name,
        })
    return assignments

def get_date_assignments(courses, datetime_from="0000-00-00 00:00:00", datetime_to="9999-12-31 23:59:59"):
    conn = __db_connect()
    cur = conn.cursor()

    try:

        query = """
            SELECT id, course_id, time, name
            FROM Assignment a
            WHERE course_id IN ({})
                AND revision = (SELECT max(a2.revision) FROM Assignment a2 WHERE a2.id = a.id)
                AND time LIKE "____-__-__ __:__:__"
                AND time >= ?
                AND time <= ?
            ORDER BY time
        """.format(','.join('?'*len(courses)))

        results = cur.execute(query, (*courses, datetime_from, datetime_to))
        assignments = __parse_assignments(results)
        
    finally:
        conn.close()

    return assignments

class Weekdays:
    SUNDAY = 0
    MONDAY = 1
    TUESDAY = 2
    WEDNESDAY = 3
    THURSDAY = 4
    FRIDAY = 5
    SATURDAY = 6


def get_weekly_assignments(courses, weekday_from=SUNDAY, time_from="00:00:00", weekday_to=SATURDAY, time_to="23:59:59"):
    conn = __db_connect()
    cur = conn.cursor()

    try:

        if weekday_from <= weekday_to:
            query = """
                SELECT id, course_id, time, name
                FROM Assignment a
                WHERE course_id IN ({})
                    AND revision = (SELECT max(a2.revision) FROM Assignment a2 WHERE a2.id = a.id)
                    AND time LIKE "WEEKDAY-_ __:__:__"
                    AND time >= "WEEKDAY-" || ? || " " || ?
                    AND time <= "WEEKDAY-" || ? || " " || ?
                ORDER BY time
            """.format(','.join('?'*len(courses))) # after from and before to.
        else:
            query = """
                SELECT id, course_id, time, name
                FROM Assignment a
                WHERE course_id IN ({})
                    AND revision = (SELECT max(a2.revision) FROM Assignment a2 WHERE a2.id = a.id)
                    AND time LIKE "WEEKDAY-_ __:__:__"
                    AND (
                        time >= "WEEKDAY-" || ? || " " || ?
                        OR time <= "WEEKDAY-" || ? || " " || ?
                    )
                ORDER BY time
            """.format(','.join('?'*len(courses))) # after from or before to


        results = cur.execute(query, (*courses, weekday_from, time_from, weekday_to, time_to,))
        assignments = __parse_assignments(results)
        
    finally:
        conn.close()

    return assignments

def add_assignment(course_id, datetime_str, name, username):
    conn = __db_connect()
    cur = conn.cursor()
    try:
        query = """
            INSERT INTO Assignment (id, revision, course_id, time, name, editor_username)
            VALUES (
                coalesce ((SELECT max(id) FROM Assignment), 0) + 1,
                1, ?, ?, ?, ?
            )
        """

        cur.execute(query, (course_id, datetime_str, name, username))

        conn.commit()

    finally:
        conn.close()

def update_assignment(id, datetime_str, name, username):
    conn = __db_connect()
    cur = conn.cursor()

    try:
        query = """
            INSERT INTO Assignment (id, revision, course_id, time, name, editor_username)
            VALUES (
                ?,
                (SELECT max(revision) FROM Assignment WHERE id = ?) + 1,
                (SELECT course_id FROM Assignment WHERE id = ?),
                ?, ?, ?
            )
        """
        cur.execute(query, (id, id, id, datetime_str, name, username))

        conn.commit()

    finally:
        conn.close()

def delete_assignment(id, email):
    conn = __db_connect()
    cur = conn.cursor()

    try:
        query = """
            INSERT INTO Assignment (id, revision, deleted, editor_username)
            VALUES (
                ?,
                (SELECT max(revision) FROM Assignment WHERE id = ?) + 1,
                1, ?
            )
        """
        cur.execute(query, (id, id, email))

        conn.commit()

    finally:
        conn.close()

#day = "WEEKDAY." || strftime("%w", ?)


'''

def xxxxxx():
    conn = __db_connect()
    cur = conn.cursor()

    try:
        query = """
            
        """

        cur.execute(query)

        conn.commit()
    
    finally:
        conn.close()


'''