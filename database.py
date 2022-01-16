from asyncio import InvalidStateError
import sqlite3
from typing import final
from unittest import removeResult

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
            SELECT cl.id, cl.type, cl.precedence, cl.url, cl.name, cl.verified
            FROM CourseLink cl
            WHERE cl.course_id = ?
                AND cl.deleted = 0
                AND revision = (SELECT max(cl2.revision) FROM CourseLink cl2 WHERE cl2.id = cl.id)
            ORDER BY cl.precedence ASC
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